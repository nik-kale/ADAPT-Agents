"""
Authentication and Authorization for ADAPT-Agents API

Provides:
- API key validation from environment configuration
- Audit logging for authentication attempts
- Rate limiting integration
"""

from fastapi import Security, HTTPException, Request
from fastapi.security import APIKeyHeader
from typing import Optional
import logging
from datetime import datetime

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

