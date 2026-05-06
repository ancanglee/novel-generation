"""Per-process Cancel cache (TTL 8s) — reads DDB Job.cancel_requested on miss."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from cachetools import TTLCache

from novelgen_obs import get_logger

log = get_logger("worker-generation.cancel")

CANCEL_TTL_SECONDS = 8


class JobReader(Protocol):
    async def is_canceled(self, team_id: UUID, job_id: UUID) -> bool: ...


class CancelCache:
    def __init__(self, reader: JobReader) -> None:
        self._reader = reader
        self._cache: TTLCache[str, bool] = TTLCache(maxsize=1000, ttl=CANCEL_TTL_SECONDS)

    async def is_canceled(self, team_id: UUID, job_id: UUID) -> bool:
        key = f"{team_id}:{job_id}"
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        value = await self._reader.is_canceled(team_id, job_id)
        self._cache[key] = value
        return value

    def invalidate(self, team_id: UUID, job_id: UUID) -> None:
        key = f"{team_id}:{job_id}"
        self._cache.pop(key, None)
