"""
Redis caching service.
Caches GitHub API responses, repo metadata, and analysis results.
"""

import json
import redis.asyncio as redis
from typing import Optional, Any
from config import get_settings

settings = get_settings()


class CacheService:
    """Redis-based caching layer with TTL support."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value by key."""
        try:
            client = await self._get_client()
            if not client:
                return None
            value = await client.get(f"cra:{key}")
            return json.loads(value) if value else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = None):
        """Set a cached value with optional TTL."""
        try:
            client = await self._get_client()
            if not client:
                return
            serialized = json.dumps(value, default=str)
            await client.set(
                f"cra:{key}",
                serialized,
                ex=ttl or settings.CACHE_TTL,
            )
        except Exception:
            pass  # Silently fail — cache is optional

    async def delete(self, key: str):
        """Delete a cached value."""
        try:
            client = await self._get_client()
            if client:
                await client.delete(f"cra:{key}")
        except Exception:
            pass

    async def flush_pattern(self, pattern: str):
        """Delete all keys matching a pattern."""
        try:
            client = await self._get_client()
            if not client:
                return
            async for key in client.scan_iter(match=f"cra:{pattern}"):
                await client.delete(key)
        except Exception:
            pass
