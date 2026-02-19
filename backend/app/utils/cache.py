"""In-memory cache with TTL support."""

from __future__ import annotations

import asyncio
import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


class CacheKeys:
    """Centralized cache key builders for consistency across endpoints."""

    @staticmethod
    def patients(
        user_id: int, search: str | None = None, skip: int = 0, limit: int = 100
    ) -> str:
        """Cache key for patient list."""
        return f"patients:{user_id}:{search or ''}:{skip}:{limit}"

    @staticmethod
    def patients_prefix(user_id: int) -> str:
        """Prefix for invalidating all patient cache entries for a user."""
        return f"patients:{user_id}:"

    @staticmethod
    def records(
        user_id: int,
        patient_id: int | None = None,
        record_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> str:
        """Cache key for records list."""
        return f"records:{user_id}:{patient_id or 'all'}:{record_type or ''}:{skip}:{limit}"

    @staticmethod
    def records_prefix(user_id: int) -> str:
        """Prefix for invalidating all records cache entries for a user."""
        return f"records:{user_id}:"

    @staticmethod
    def documents(
        user_id: int,
        patient_id: int | None = None,
        document_type: str | None = None,
        processed_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> str:
        """Cache key for documents list."""
        return f"documents:{user_id}:{patient_id or 'all'}:{document_type or ''}:{processed_only}:{skip}:{limit}"

    @staticmethod
    def documents_prefix(user_id: int) -> str:
        """Prefix for invalidating all documents cache entries for a user."""
        return f"documents:{user_id}:"

    @staticmethod
    def memory_stats(user_id: int, patient_id: int | None = None) -> str:
        """Cache key for memory statistics."""
        return f"memory_stats:{user_id}:{patient_id or 'all'}"

    @staticmethod
    def memory_stats_prefix(user_id: int) -> str:
        """Prefix for invalidating all memory stats cache entries for a user."""
        return f"memory_stats:{user_id}:"


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
