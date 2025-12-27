"""
Rate Limiting for ADAPT-Agents API

Supports both in-memory and Redis-based distributed rate limiting
with sliding window algorithm and per-tier limits.
"""

import time
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from config.settings import get_settings

logger = logging.getLogger(__name__)


class RateLimiterBackend(ABC):
    """Abstract base class for rate limiter backends"""
    
    @abstractmethod
    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Check if request is allowed under rate limit
        
        Args:
            key: Rate limit key (e.g., API key)
            limit: Maximum requests per window
            window: Time window in seconds
        
        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        pass
    
    @abstractmethod
    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests in current window"""
        pass


class MemoryRateLimiter(RateLimiterBackend):
    """In-memory rate limiter using sliding window"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Check if request is allowed under rate limit"""
        now = time.time()
        
        # Clean old requests (sliding window)
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < window
        ]
        
        remaining = max(0, limit - len(self.requests[key]))
        
        # Check limit
        if len(self.requests[key]) >= limit:
            return (False, 0)
        
        # Add new request
        self.requests[key].append(now)
        return (True, remaining - 1)
    
    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests in current window"""
        now = time.time()
        active_requests = [
            req_time for req_time in self.requests[key]
            if now - req_time < window
        ]
        return max(0, limit - len(active_requests))


class RedisRateLimiter(RateLimiterBackend):
    """Redis-based distributed rate limiter using sliding window"""
    
    def __init__(self, redis_url: str):
        try:
            import redis
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis rate limiter connected: {redis_url}")
        except ImportError:
            logger.error("Redis package not installed. Install with: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Check if request is allowed using Redis sliding window
        
        Uses Redis sorted set with timestamps as scores for efficient
        sliding window implementation.
        """
        try:
            now = time.time()
            window_start = now - window
            redis_key = f"rate_limit:{key}"
            
            # Use Redis transaction for atomicity
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Count current requests
            pipe.zcard(redis_key)
            
            # Execute pipeline
            results = pipe.execute()
            current_count = results[1]
            
            remaining = max(0, limit - current_count)
            
            # Check if allowed
            if current_count >= limit:
                return (False, 0)
            
            # Add new request with timestamp as score
            self.redis_client.zadd(redis_key, {str(now): now})
            
            # Set expiration on key (cleanup)
            self.redis_client.expire(redis_key, window * 2)
            
            return (True, remaining - 1)
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}. Allowing request.")
            # Fail open - allow request if Redis is down
            return (True, limit)
    
    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """Get remaining requests in current window"""
        try:
            now = time.time()
            window_start = now - window
            redis_key = f"rate_limit:{key}"
            
            # Remove old entries and count
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            results = pipe.execute()
            
            current_count = results[1]
            return max(0, limit - current_count)
            
        except Exception as e:
            logger.error(f"Redis get_remaining error: {e}")
            return limit


class RateLimiter:
    """
    Main rate limiter with pluggable backend
    
    Supports per-tier rate limits and automatic backend selection
    based on configuration.
    """
    
    # Tier-based limits (requests per minute)
    TIER_LIMITS = {
        "free": 100,
        "premium": 1000,
        "enterprise": 10000,
        "unlimited": 999999
    }
    
    def __init__(self, backend: Optional[RateLimiterBackend] = None):
        if backend is None:
            # Auto-select backend based on configuration
            settings = get_settings()
            if settings.cache_backend == "redis" and settings.cache_redis_url:
                try:
                    backend = RedisRateLimiter(settings.cache_redis_url)
                    logger.info("Using Redis-based distributed rate limiter")
                except Exception as e:
                    logger.warning(f"Failed to initialize Redis rate limiter: {e}. Using memory backend.")
                    backend = MemoryRateLimiter()
            else:
                backend = MemoryRateLimiter()
                logger.info("Using in-memory rate limiter")
        
        self.backend = backend
        self.default_limit = 100
        self.default_window = 60
    
    def is_allowed(self, api_key: str, tier: str = "free") -> bool:
        """
        Check if request is allowed for given API key
        
        Args:
            api_key: API key making the request
            tier: Tier level (free, premium, enterprise, unlimited)
        
        Returns:
            True if request is allowed, False if rate limited
        """
        limit = self.TIER_LIMITS.get(tier, self.default_limit)
        allowed, remaining = self.backend.is_allowed(
            api_key, limit, self.default_window
        )
        return allowed
    
    def get_remaining(self, api_key: str, tier: str = "free") -> int:
        """Get remaining requests for API key"""
        limit = self.TIER_LIMITS.get(tier, self.default_limit)
        return self.backend.get_remaining(api_key, limit, self.default_window)
    
    def get_limit_info(self, api_key: str, tier: str = "free") -> Dict[str, int]:
        """Get complete rate limit information"""
        limit = self.TIER_LIMITS.get(tier, self.default_limit)
        remaining = self.get_remaining(api_key, tier)
        
        return {
            "limit": limit,
            "remaining": remaining,
            "window_seconds": self.default_window,
            "tier": tier
        }


# Global rate limiter instance
rate_limiter = RateLimiter()

