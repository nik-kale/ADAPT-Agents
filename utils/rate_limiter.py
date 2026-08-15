"""
Rate Limiting for ADAPT-Agents API

Supports both in-memory and Redis-based distributed rate limiting
with sliding window algorithm and per-tier limits.
"""

import time
import uuid
import logging
from abc import ABC, abstractmethod
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

    # Hard ceiling on distinct tracked keys. Without this, a caller sending a
    # random X-API-Key per request would grow the dict until the process OOMs.
    MAX_TRACKED_KEYS = 10_000

    def __init__(self, max_tracked_keys: int = MAX_TRACKED_KEYS):
        self.requests: Dict[str, List[float]] = {}
        self.max_tracked_keys = max_tracked_keys

    def _prune(self, now: float, window: int) -> None:
        """Drop keys whose window has fully elapsed."""
        stale = [
            key for key, times in self.requests.items()
            if not times or now - times[-1] >= window
        ]
        for key in stale:
            del self.requests[key]

    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Check if request is allowed under rate limit"""
        now = time.time()

        # Clean old requests (sliding window). Use .get() so that merely
        # observing an unknown key never creates an entry.
        active = [
            req_time for req_time in self.requests.get(key, ())
            if now - req_time < window
        ]

        remaining = max(0, limit - len(active))

        # Check limit
        if len(active) >= limit:
            self.requests[key] = active
            return (False, 0)

        # Bound total tracked keys before inserting a new one.
        if key not in self.requests and len(self.requests) >= self.max_tracked_keys:
            self._prune(now, window)
            if len(self.requests) >= self.max_tracked_keys:
                logger.warning(
                    "Rate limiter key table full (%d keys); allowing request without tracking.",
                    self.max_tracked_keys
                )
                return (True, remaining - 1)

        # Add new request
        active.append(now)
        self.requests[key] = active
        return (True, remaining - 1)

    def get_remaining(self, key: str, limit: int, window: int) -> int:
        """
        Get remaining requests in current window.

        Read-only: never inserts a key, so unauthenticated probes cannot grow
        the tracking table.
        """
        now = time.time()
        active_requests = [
            req_time for req_time in self.requests.get(key, ())
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
            # Register the atomic sliding-window script once.
            self._sliding_window_script = self.redis_client.register_script(
                self._SLIDING_WINDOW_LUA
            )
            logger.info(f"Redis rate limiter connected: {redis_url}")
        except ImportError:
            logger.error("Redis package not installed. Install with: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    # Atomic check-and-admit. Running prune + count + conditional insert inside a
    # single Lua script makes the whole decision atomic; a pipeline is NOT enough,
    # because N concurrent workers can each read count == limit-1 and then all
    # insert, admitting limit + N - 1 requests in one window.
    _SLIDING_WINDOW_LUA = """
    local key      = KEYS[1]
    local now      = tonumber(ARGV[1])
    local window   = tonumber(ARGV[2])
    local limit    = tonumber(ARGV[3])
    local member   = ARGV[4]

    redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
    local count = redis.call('ZCARD', key)

    if count >= limit then
        redis.call('EXPIRE', key, window * 2)
        return {0, 0}
    end

    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window * 2)
    return {1, limit - count - 1}
    """

    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Check if request is allowed using Redis sliding window.

        Uses a Redis sorted set with timestamps as scores, driven by a Lua
        script so that the prune/count/insert sequence is atomic across
        concurrent workers.
        """
        try:
            now = time.time()
            redis_key = f"rate_limit:{key}"

            # Unique member per request. Using str(now) alone collides when two
            # requests land on the same float timestamp, which undercounts.
            member = f"{now}:{uuid.uuid4().hex}"

            allowed, remaining = self._sliding_window_script(
                keys=[redis_key],
                args=[now, window, limit, member]
            )

            return (bool(allowed), int(remaining))

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

