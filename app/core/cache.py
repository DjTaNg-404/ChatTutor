import hashlib
import json
import time
from typing import Any, Dict, Optional, Set


class TTLCache:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._data: Dict[str, Any] = {}

    def _expired(self, ts: float) -> bool:
        return (time.time() - ts) >= self.ttl

    def get(self, key: str):
        if key not in self._data:
            return None
        value, ts = self._data[key]
        if self._expired(ts):
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any):
        self._data[key] = (value, time.time())

    def clear(self):
        self._data.clear()


class RetrievalCache(TTLCache):
    def make_key(self, query: str) -> str:
        return hashlib.md5(query.strip().encode("utf-8")).hexdigest()


class GenerationCache(TTLCache):
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

    def set(self, key: str, value: Any, session_id: Optional[str] = None):
        super().set(key, value)
        if session_id:
            self._session_index.setdefault(session_id, set()).add(key)

    def clear_session(self, session_id: str):
        keys = self._session_index.get(session_id, set())
        for k in keys:
            self._data.pop(k, None)
        self._session_index.pop(session_id, None)


retrieval_cache = RetrievalCache(ttl=180)
generation_cache = GenerationCache(ttl=300)
