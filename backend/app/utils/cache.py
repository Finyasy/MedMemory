from __future__ import annotations

import asyncio
import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


async def get_cached(key: str) -> Any | None:
    now = time.monotonic()
    async with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if now >= expires_at:
            _cache.pop(key, None)
            return None
        return value


async def set_cached(key: str, value: Any, ttl_seconds: int) -> None:
    expires_at = time.monotonic() + ttl_seconds
    async with _cache_lock:
        _cache[key] = (expires_at, value)


async def clear_cache(prefix: str | None = None) -> None:
    async with _cache_lock:
        if prefix is None:
            _cache.clear()
            return
        for key in list(_cache.keys()):
            if key.startswith(prefix):
                _cache.pop(key, None)
