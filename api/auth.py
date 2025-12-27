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

    # Check rate limit
    if not rate_limiter.is_allowed(api_key):
        auth_logger.warning(
            f"Rate limit exceeded: key={api_key[:8]}... | ip={client_ip} | time={timestamp}"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s"
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

# WebSocket token storage (in-memory, consider Redis for production)
_ws_tokens = {}  # {token_hash: {api_key, expires_at, analysis_ids}}

# Token configuration
WS_TOKEN_EXPIRY_MINUTES = 15
WS_TOKEN_LENGTH = 32


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

    _ws_tokens[token_hash] = {
        "api_key": api_key,
        "expires_at": expires_at,
        "analysis_ids": analysis_ids or [],
        "created_at": datetime.utcnow()
    }

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
    token_info = _ws_tokens.get(token_hash)

    if not token_info:
        auth_logger.warning(f"WebSocket authentication failed: token not found")
        raise HTTPException(status_code=4001, detail="Invalid WebSocket token")

    # Check expiration
    if datetime.utcnow() > token_info["expires_at"]:
        auth_logger.warning(f"WebSocket authentication failed: token expired")
        del _ws_tokens[token_hash]
        raise HTTPException(status_code=4001, detail="WebSocket token expired")

    # Check analysis_id access if specified
    if analysis_id and token_info["analysis_ids"]:
        if analysis_id not in token_info["analysis_ids"]:
            auth_logger.warning(
                f"WebSocket authentication failed: unauthorized analysis_id | "
                f"requested={analysis_id} | allowed={token_info['analysis_ids']}"
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
    """Remove expired WebSocket tokens from memory"""
    now = datetime.utcnow()
    expired = [
        token_hash for token_hash, info in _ws_tokens.items()
        if now > info["expires_at"]
    ]

    for token_hash in expired:
        del _ws_tokens[token_hash]

    if expired:
        auth_logger.debug(f"Cleaned up {len(expired)} expired WebSocket tokens")

