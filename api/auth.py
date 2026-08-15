"""
Authentication and Authorization for ADAPT-Agents API

Provides:
- API key validation from environment configuration
- Audit logging for authentication attempts
- Rate limiting integration
"""

from fastapi import Security, HTTPException, Request
from fastapi.security import APIKeyHeader
from typing import Optional, List
import logging
from datetime import datetime, timedelta
import secrets
import hashlib

from config.settings import get_settings
from utils.rate_limiter import rate_limiter

# Rate limiting configuration (defaults, can be overridden)
RATE_LIMIT_REQUESTS = 100  # requests per minute per API key
RATE_LIMIT_WINDOW = 60  # seconds

# API key header definition
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Audit logger for authentication events
auth_logger = logging.getLogger("adapt.auth")
auth_logger.setLevel(logging.INFO)


async def get_api_key(
    api_key: str = Security(api_key_header),
    request: Optional[Request] = None
) -> str:
    """
    Validate API key from environment configuration

    Supports:
    - Environment-based key management via ADAPT_API_KEYS
    - Audit logging for authentication attempts
    - Key tier identification

    Usage:
        Set environment variable:
        ADAPT_API_KEYS='{"your-key-123": {"name": "prod", "tier": "premium"}}'
    """
    settings = get_settings()

    # Get valid API keys from settings
    valid_api_keys = settings.api_keys

    # Fallback to demo keys if no keys configured (development only)
    if not valid_api_keys:
        valid_api_keys = {
            "demo-key-12345": {"name": "demo", "tier": "free"}
        }
        auth_logger.warning(
            "No API keys configured. Using demo key. "
            "Set ADAPT_API_KEYS environment variable for production."
        )

    # Log authentication attempt
    client_ip = request.client.host if request else "unknown"
    timestamp = datetime.utcnow().isoformat()

    if not api_key or api_key not in valid_api_keys:
        auth_logger.warning(
            f"Authentication failed: invalid_key | ip={client_ip} | "
            f"key={'missing' if not api_key else 'invalid'} | time={timestamp}"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Provide X-API-Key header."
        )

    # Check rate limit with tier-based limits
    key_info = valid_api_keys.get(api_key, {})
    tier = key_info.get('tier', 'free')
    
    if not rate_limiter.is_allowed(api_key, tier):
        limit_info = rate_limiter.get_limit_info(api_key, tier)
        auth_logger.warning(
            f"Rate limit exceeded: key={api_key[:8]}... | tier={tier} | "
            f"limit={limit_info['limit']}/min | ip={client_ip} | time={timestamp}"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Tier: {tier}, Limit: {limit_info['limit']} requests per {limit_info['window_seconds']}s"
        )

    # Log successful authentication
    key_info = valid_api_keys.get(api_key, {})
    auth_logger.info(
        f"Authentication success: key={api_key[:8]}... | "
        f"tier={key_info.get('tier', 'unknown')} | ip={client_ip} | time={timestamp}"
    )

    return api_key


def get_api_key_info(api_key: str) -> dict:
    """Get information about an API key"""
    settings = get_settings()
    valid_api_keys = settings.api_keys

    if not valid_api_keys:
        valid_api_keys = {
            "demo-key-12345": {"name": "demo", "tier": "free"}
        }

    return valid_api_keys.get(api_key, {})


# === WebSocket Authentication ===

# Token configuration
WS_TOKEN_EXPIRY_MINUTES = 15
WS_TOKEN_LENGTH = 32


class _WSTokenStore:
    """
    Storage for short-lived WebSocket tokens.

    Backed by Redis when configured, otherwise by a process-local dict.

    A process-local dict is only correct for single-process deployments: under
    `uvicorn --workers N`, POST /ws/token mints the token in one worker while
    the subsequent WebSocket upgrade may be routed to another, which would
    reject a perfectly valid token. Redis makes the store shared.
    """

    _KEY_PREFIX = "ws_token:"

    def __init__(self):
        self._memory = {}
        self._redis = None

        settings = get_settings()
        if settings.cache_backend == "redis" and settings.cache_redis_url:
            try:
                import redis
                client = redis.from_url(
                    settings.cache_redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                client.ping()
                self._redis = client
                auth_logger.info("WebSocket token store using Redis (multi-worker safe)")
            except Exception as e:
                auth_logger.warning(
                    f"WebSocket token store failed to reach Redis ({e}); falling back "
                    f"to in-process memory. This is NOT safe with multiple workers."
                )

        if self._redis is None:
            auth_logger.info("WebSocket token store using in-process memory")

    def set(self, token_hash: str, info: dict, ttl_seconds: int) -> None:
        if self._redis is not None:
            import json
            payload = dict(info)
            payload["expires_at"] = info["expires_at"].isoformat()
            payload["created_at"] = info["created_at"].isoformat()
            self._redis.setex(
                f"{self._KEY_PREFIX}{token_hash}", ttl_seconds, json.dumps(payload)
            )
        else:
            self._memory[token_hash] = info

    def get(self, token_hash: str) -> Optional[dict]:
        if self._redis is not None:
            import json
            raw = self._redis.get(f"{self._KEY_PREFIX}{token_hash}")
            if raw is None:
                return None
            payload = json.loads(raw)
            payload["expires_at"] = datetime.fromisoformat(payload["expires_at"])
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
            return payload
        return self._memory.get(token_hash)

    def delete(self, token_hash: str) -> None:
        if self._redis is not None:
            self._redis.delete(f"{self._KEY_PREFIX}{token_hash}")
        else:
            self._memory.pop(token_hash, None)

    def purge_expired(self) -> int:
        """Redis expires keys itself; only the memory backend needs sweeping."""
        if self._redis is not None:
            return 0
        now = datetime.utcnow()
        expired = [h for h, info in self._memory.items() if now > info["expires_at"]]
        for token_hash in expired:
            del self._memory[token_hash]
        return len(expired)


_ws_token_store: Optional[_WSTokenStore] = None


def _get_ws_token_store() -> _WSTokenStore:
    """Lazily construct the token store so settings are read at first use."""
    global _ws_token_store
    if _ws_token_store is None:
        _ws_token_store = _WSTokenStore()
    return _ws_token_store


def generate_ws_token(api_key: str, analysis_ids: Optional[List[str]] = None) -> str:
    """
    Generate a short-lived WebSocket token

    Args:
        api_key: API key to associate with the token
        analysis_ids: Optional list of analysis IDs this token can access

    Returns:
        WebSocket token string
    """
    token = secrets.token_urlsafe(WS_TOKEN_LENGTH)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    expires_at = datetime.utcnow() + timedelta(minutes=WS_TOKEN_EXPIRY_MINUTES)

    _get_ws_token_store().set(
        token_hash,
        {
            "api_key": api_key,
            "expires_at": expires_at,
            "analysis_ids": analysis_ids or [],
            "created_at": datetime.utcnow()
        },
        ttl_seconds=WS_TOKEN_EXPIRY_MINUTES * 60
    )

    # Clean up expired tokens
    _cleanup_expired_tokens()

    auth_logger.info(
        f"WebSocket token generated: api_key={api_key[:8]}... | "
        f"expires={expires_at.isoformat()} | analysis_ids={len(analysis_ids or [])}"
    )

    return token


def verify_ws_token(token: str, analysis_id: Optional[str] = None) -> dict:
    """
    Verify a WebSocket token and check permissions

    Args:
        token: WebSocket token to verify
        analysis_id: Optional analysis ID to check access for

    Returns:
        Token info dict if valid

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not token:
        raise HTTPException(status_code=4001, detail="Missing WebSocket token")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    store = _get_ws_token_store()
    token_info = store.get(token_hash)

    if not token_info:
        auth_logger.warning(f"WebSocket authentication failed: token not found")
        raise HTTPException(status_code=4001, detail="Invalid WebSocket token")

    # Check expiration
    if datetime.utcnow() > token_info["expires_at"]:
        auth_logger.warning(f"WebSocket authentication failed: token expired")
        store.delete(token_hash)
        raise HTTPException(status_code=4001, detail="WebSocket token expired")

    # Enforce analysis scoping.
    #
    # A token carrying a non-empty analysis_ids list is RESTRICTED: it grants
    # access only to those analyses. Previously the check was skipped whenever
    # analysis_id was falsy, so a restricted token could reach unscoped
    # endpoints (/ws/broadcast, or /ws/agent/{name} with analysis_id omitted)
    # and observe traffic for every analysis in the system.
    allowed_ids = token_info.get("analysis_ids") or []
    if allowed_ids:
        if not analysis_id:
            auth_logger.warning(
                f"WebSocket authentication failed: scoped token used on an "
                f"unscoped endpoint | allowed={allowed_ids}"
            )
            raise HTTPException(
                status_code=4003,
                detail=(
                    "This token is restricted to specific analyses and cannot be "
                    "used on endpoints that are not scoped to a single analysis."
                )
            )
        if analysis_id not in allowed_ids:
            auth_logger.warning(
                f"WebSocket authentication failed: unauthorized analysis_id | "
                f"requested={analysis_id} | allowed={allowed_ids}"
            )
            raise HTTPException(
                status_code=4003,
                detail=f"Token not authorized for analysis {analysis_id}"
            )

    auth_logger.info(
        f"WebSocket authentication success: api_key={token_info['api_key'][:8]}... | "
        f"analysis_id={analysis_id or 'any'}"
    )

    return token_info


def _cleanup_expired_tokens():
    """Remove expired WebSocket tokens from the store"""
    removed = _get_ws_token_store().purge_expired()

    if removed:
        auth_logger.debug(f"Cleaned up {removed} expired WebSocket tokens")

