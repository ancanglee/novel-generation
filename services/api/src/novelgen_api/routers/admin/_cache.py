"""Minute-bucketed TTLCache for /admin/monitoring/summary (D3=A)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from cachetools import TTLCache

_CACHE: TTLCache[tuple[int, int], dict[str, Any]] = TTLCache(maxsize=32, ttl=60)


def minute_bucket(dt: datetime) -> int:
    """Align datetime to the start of its UTC minute → epoch-minute int."""
    normalized = dt.astimezone(UTC).replace(second=0, microsecond=0)
    return int(normalized.timestamp() // 60)


def cache_get(from_: datetime, to: datetime) -> dict[str, Any] | None:
    return _CACHE.get((minute_bucket(from_), minute_bucket(to)))


def cache_set(from_: datetime, to: datetime, value: dict[str, Any]) -> None:
    _CACHE[(minute_bucket(from_), minute_bucket(to))] = value


def cache_clear() -> None:
    """Test helper."""
    _CACHE.clear()
