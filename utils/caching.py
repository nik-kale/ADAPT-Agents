"""
Caching utilities for agent results
"""

import hashlib
import json
from typing import Optional, Any
from abc import ABC, abstractmethod
from schemas import BaseAgentInput, BaseAgentOutput


class CacheBackend(ABC):
    """Abstract cache backend"""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int):
        """Set value in cache with TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str):
        """Delete value from cache"""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache implementation"""

    def __init__(self):
        self._cache: dict = {}
        self._expiry: dict = {}

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        import time
        if key in self._cache:
            if key in self._expiry and time.time() > self._expiry[key]:
                # Expired
                del self._cache[key]
                del self._expiry[key]
                return None
            return self._cache[key]
        return None

    async def set(self, key: str, value: str, ttl: int):
        """Set value with TTL"""
        import time
        self._cache[key] = value
        self._expiry[key] = time.time() + ttl

    async def delete(self, key: str):
        """Delete from cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._expiry:
            del self._expiry[key]


class RedisCache(CacheBackend):
    """Redis cache implementation"""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None

    async def connect(self):
        """Connect to Redis"""
        try:
            import aioredis
            self.redis = await aioredis.from_url(self.redis_url)
        except ImportError:
            raise ImportError("aioredis not installed. Install with: pip install aioredis")

    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self.redis:
            await self.connect()
        value = await self.redis.get(key)
        return value.decode() if value else None

    async def set(self, key: str, value: str, ttl: int):
        """Set value with TTL"""
        if not self.redis:
            await self.connect()
        await self.redis.setex(key, ttl, value)

    async def delete(self, key: str):
        """Delete from Redis"""
        if not self.redis:
            await self.connect()
        await self.redis.delete(key)


class AgentCache:
    """Cache for agent execution results"""

    def __init__(self, backend: CacheBackend, ttl: int = 300):
        self.backend = backend
        self.ttl = ttl

    def _generate_key(self, agent_name: str, input_data: BaseAgentInput) -> str:
        """Generate cache key from input"""
        # Create deterministic hash
        input_dict = input_data.dict()
        input_json = json.dumps(input_dict, sort_keys=True)
        hash_digest = hashlib.sha256(input_json.encode()).hexdigest()
        return f"agent:{agent_name}:{hash_digest}"

    async def get(
        self,
        agent_name: str,
        input_data: BaseAgentInput
    ) -> Optional[BaseAgentOutput]:
        """Get cached result"""
        key = self._generate_key(agent_name, input_data)
        cached_json = await self.backend.get(key)

        if cached_json:
            try:
                cached_dict = json.loads(cached_json)
                return BaseAgentOutput(**cached_dict)
            except Exception:
                # Invalid cache entry
                await self.backend.delete(key)

        return None

    async def set(
        self,
        agent_name: str,
        input_data: BaseAgentInput,
        result: BaseAgentOutput
    ):
        """Cache result"""
        key = self._generate_key(agent_name, input_data)
        result_json = result.json()
        await self.backend.set(key, result_json, self.ttl)

    async def clear(self, agent_name: Optional[str] = None):
        """Clear cache for specific agent or all"""
        # Note: Requires backend-specific implementation for pattern matching
        pass


# Global cache instance
_cache: Optional[AgentCache] = None


def get_cache() -> AgentCache:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        from config.settings import get_settings
        settings = get_settings()

        if settings.cache_backend == "redis" and settings.cache_redis_url:
            backend = RedisCache(settings.cache_redis_url)
        else:
            backend = MemoryCache()

        _cache = AgentCache(backend, ttl=settings.cache_ttl_seconds)

    return _cache
