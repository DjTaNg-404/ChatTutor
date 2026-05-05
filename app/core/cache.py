"""
TTL Cache for ChatTutor.

Provides in-memory TTL cache with Redis fallback for production deployment.
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional, Set

from app.core.redis_client import generation_cache as redis_generation_cache
from app.core.redis_client import retrieval_cache as redis_retrieval_cache


class TTLCache:
    """In-memory TTL cache (fallback when Redis is unavailable)."""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._data: Dict[str, Any] = {}

    def _expired(self, ts: float) -> bool:
        return (time.time() - ts) >= self.ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None
        value, ts = self._data[key]
        if self._expired(ts):
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (value, time.time())

    def clear(self) -> None:
        self._data.clear()


class RetrievalCache(TTLCache):
    """Cache for RAG retrieval results."""

    def make_key(self, query: str) -> str:
        return hashlib.md5(query.strip().encode("utf-8")).hexdigest()


class GenerationCache(TTLCache):
    """Cache for LLM generation results with session indexing."""

    def __init__(self, ttl: int = 300):
        super().__init__(ttl=ttl)
        self._session_index: Dict[str, Set[str]] = {}

    def make_key(
        self,
        session_id: str,
        node: str,
        prompt: str,
        history_sig: str,
        tool_sig: str = "",
    ) -> str:
        payload = {
            "sid": session_id,
            "node": node,
            "prompt": prompt,
            "history": history_sig,
            "tool": tool_sig,
        }
        return hashlib.md5(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def set(self, key: str, value: Any, session_id: Optional[str] = None) -> None:
        super().set(key, value)
        if session_id:
            self._session_index.setdefault(session_id, set()).add(key)

    def clear_session(self, session_id: str) -> None:
        keys = self._session_index.get(session_id, set())
        for k in keys:
            self._data.pop(k, None)
        self._session_index.pop(session_id, None)


# Global cache instances
# In production, these will use Redis; fallback to in-memory if Redis unavailable
retrieval_cache = RetrievalCache(ttl=180)
generation_cache = GenerationCache(ttl=300)


# ===== Async Redis-backed cache functions =====

async def async_get_generation_cache(key: str) -> Optional[Any]:
    """Get value from generation cache (Redis-backed)."""
    try:
        return await redis_generation_cache.get(key)
    except Exception:
        return generation_cache.get(key)


async def async_set_generation_cache(key: str, value: Any, session_id: Optional[str] = None) -> None:
    """Set value in generation cache (Redis-backed)."""
    try:
        await redis_generation_cache.set(key, value, session_id)
    except Exception:
        generation_cache.set(key, value)


async def async_get_retrieval_cache(key: str) -> Optional[Any]:
    """Get value from retrieval cache (Redis-backed)."""
    try:
        return await redis_retrieval_cache.get(key)
    except Exception:
        return retrieval_cache.get(key)


async def async_set_retrieval_cache(key: str, value: Any) -> None:
    """Set value in retrieval cache (Redis-backed)."""
    try:
        await redis_retrieval_cache.set(key, value)
    except Exception:
        retrieval_cache.set(key, value)


async def async_clear_session_cache(session_id: str) -> None:
    """Clear all cache entries for a session (Redis-backed)."""
    try:
        await redis_generation_cache.clear_session(session_id)
    except Exception:
        generation_cache.clear_session(session_id)
