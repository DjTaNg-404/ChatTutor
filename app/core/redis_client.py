"""
Redis Async Client for ChatTutor.

Provides:
- Redis connection pool using redis.asyncio
- get_redis(): dependency injection for FastAPI routes
- TTL cache implementation
"""

import json
import time
from typing import Any, Optional, AsyncGenerator
from redis.asyncio import Redis, ConnectionPool

from app.core.config import settings


# Redis connection pool
redis_pool: Optional[ConnectionPool] = None


def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool."""
    global redis_pool
    if redis_pool is None:
        redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return redis_pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    FastAPI dependency for Redis client.

    Usage:
        @router.get("/cache")
        async def get_cache(redis: Redis = Depends(get_redis)):
            ...
    """
    redis = Redis(connection_pool=get_redis_pool())
    try:
        yield redis
    finally:
        await redis.close()


async def init_redis() -> None:
    """Initialize Redis connection."""
    redis = Redis(connection_pool=get_redis_pool())
    try:
        await redis.ping()
        print(f"✅ Redis connected: {settings.REDIS_URL}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
    finally:
        await redis.close()


async def close_redis() -> None:
    """Close Redis connections."""
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


class RedisTTLCache:
    """
    TTL Cache implementation using Redis.

    Supports:
    - Automatic expiration
    - Session-based invalidation
    """

    def __init__(self, ttl: int = 300, prefix: str = "cache"):
        self.ttl = ttl
        self.prefix = prefix
        self._session_index_key = f"{prefix}:session_index"

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            value = await redis.get(self._make_key(key))
            return json.loads(value) if value else None
        finally:
            await redis.close()

    async def set(self, key: str, value: Any, session_id: Optional[str] = None) -> None:
        """Set value in cache with TTL."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await redis.setex(self._make_key(key), self.ttl, serialized)

            # Index by session_id for batch invalidation
            if session_id:
                await redis.hset(self._session_index_key, f"{session_id}:{key}", "1")
                # Set TTL on the index entry
                await redis.expire(self._session_index_key, self.ttl)
        finally:
            await redis.close()

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            await redis.delete(self._make_key(key))
            # Remove from session index
            await redis.hdel(self._session_index_key, f"{session_id}:{key}")
        finally:
            await redis.close()

    async def clear_session(self, session_id: str) -> None:
        """Clear all cache entries for a session."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            # Get all keys for this session
            keys = await redis.hkeys(self._session_index_key)
            session_keys = [k for k in keys if k.startswith(f"{session_id}:")]

            if session_keys:
                # Delete all session keys
                real_keys = [self._make_key(k.split(":", 1)[1]) for k in session_keys]
                await redis.delete(*real_keys)
                # Remove from index
                await redis.hdel(self._session_index_key, *session_keys)
        finally:
            await redis.close()

    async def clear(self) -> None:
        """Clear all cache entries."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            keys = await redis.keys(f"{self.prefix}:*")
            if keys:
                await redis.delete(*keys)
            await redis.delete(self._session_index_key)
        finally:
            await redis.close()


class RedisSessionLock:
    """
    Distributed session lock using Redis SETNX.

    Prevents concurrent summarization of the same session.
    """

    LOCK_PREFIX = "lock:session"
    DEFAULT_TIMEOUT = 60  # seconds

    @classmethod
    async def acquire(cls, session_id: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        Acquire lock for a session.

        Returns True if lock acquired, False if already locked.
        """
        redis = Redis(connection_pool=get_redis_pool())
        try:
            lock_key = f"{cls.LOCK_PREFIX}:{session_id}"
            # SETNX with TTL
            acquired = await redis.set(lock_key, "1", nx=True, ex=timeout)
            return bool(acquired)
        finally:
            await redis.close()

    @classmethod
    async def release(cls, session_id: str) -> None:
        """Release lock for a session."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            lock_key = f"{cls.LOCK_PREFIX}:{session_id}"
            await redis.delete(lock_key)
        finally:
            await redis.close()

    @classmethod
    async def is_locked(cls, session_id: str) -> bool:
        """Check if session is locked."""
        redis = Redis(connection_pool=get_redis_pool())
        try:
            lock_key = f"{cls.LOCK_PREFIX}:{session_id}"
            return await redis.exists(lock_key) > 0
        finally:
            await redis.close()


# Global cache instances
generation_cache = RedisTTLCache(ttl=300, prefix="generation")
retrieval_cache = RedisTTLCache(ttl=180, prefix="retrieval")
