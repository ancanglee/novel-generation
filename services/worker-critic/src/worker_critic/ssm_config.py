"""SSM parameter cache with periodic refresh.

Worker reads `/novelgen/{env}/config/*` and refreshes every 60 seconds.
Thread-safe for asyncio usage via a single-writer lock.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import aioboto3


@dataclass
class _Entry:
    value: str
    fetched_at: float


class SsmConfigCache:
    def __init__(
        self,
        prefix: str,
        refresh_interval: float = 60.0,
        region: str = "us-east-1",
    ) -> None:
        self._prefix = prefix.rstrip("/")
        self._refresh_interval = refresh_interval
        self._region = region
        self._entries: dict[str, _Entry] = {}
        self._lock = asyncio.Lock()
        self._session = aioboto3.Session()

    def _key(self, name: str) -> str:
        return f"{self._prefix}/{name.lstrip('/')}"

    async def _fetch(self, name: str) -> str:
        full = self._key(name)
        async with self._session.client("ssm", region_name=self._region) as ssm:
            resp = await ssm.get_parameter(Name=full, WithDecryption=False)
        return resp["Parameter"]["Value"]

    async def _maybe_refresh(self, name: str) -> str:
        now = time.monotonic()
        entry = self._entries.get(name)
        if entry and (now - entry.fetched_at) < self._refresh_interval:
            return entry.value
        async with self._lock:
            entry = self._entries.get(name)
            if entry and (now - entry.fetched_at) < self._refresh_interval:
                return entry.value
            value = await self._fetch(name)
            self._entries[name] = _Entry(value=value, fetched_at=now)
            return value

    async def get_str(self, name: str, default: str) -> str:
        try:
            return await self._maybe_refresh(name)
        except Exception:
            return default

    async def get_int(self, name: str, default: int) -> int:
        raw = await self.get_str(name, str(default))
        try:
            return int(raw)
        except ValueError:
            return default
