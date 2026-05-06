"""Cross-Worker Browser slot counter (I2=B).

Single item in novelgen_*_jobs table:
  pk=COUNTER, sk=BROWSER_CONCURRENCY
  { current_count, max_count, holders[{job_id, acquired_at}] }

Acquire uses conditional update; release subtracts 1.
Zombie reclamation via periodic cleanup (Lambda) or startup scan.
"""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

import aioboto3
from novelgen_types.errors import NovelGenError


class BrowserSlotUnavailable(NovelGenError):
    error_code = "BROWSER_SLOT_UNAVAILABLE"
    http_status = 503


_PK = "COUNTER"
_SK = "BROWSER_CONCURRENCY"


class BrowserPool:
    def __init__(self, table_name: str, region: str = "us-east-1", max_attempts: int = 10) -> None:
        self._table_name = table_name
        self._region = region
        self._max_attempts = max_attempts
        self._session = aioboto3.Session()

    async def acquire(self, job_id: str) -> None:
        """Try to acquire a slot. Raises BrowserSlotUnavailable after max_attempts."""
        now = datetime.now(tz=UTC).isoformat()
        for attempt in range(self._max_attempts):
            async with self._session.resource("dynamodb", region_name=self._region) as ddb:
                table = await ddb.Table(self._table_name)
                try:
                    await table.update_item(
                        Key={"pk": _PK, "sk": _SK},
                        UpdateExpression=(
                            "SET current_count = current_count + :one, "
                            "holders = list_append(if_not_exists(holders, :empty), :h)"
                        ),
                        ConditionExpression="current_count < max_count",
                        ExpressionAttributeValues={
                            ":one": 1,
                            ":empty": [],
                            ":h": [{"job_id": job_id, "acquired_at": now}],
                        },
                    )
                    return
                except ddb.meta.client.exceptions.ConditionalCheckFailedException:
                    pass
            # Exponential backoff with jitter (base 1s → cap 8s)
            delay = min(8.0, 0.5 * (2**attempt)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
        raise BrowserSlotUnavailable(f"no slot after {self._max_attempts} retries", job_id=job_id)

    async def release(self, job_id: str) -> None:
        """Release a slot. Best-effort; does not raise."""
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            # First fetch current holders, filter, conditional write-back
            resp = await table.get_item(Key={"pk": _PK, "sk": _SK}, ConsistentRead=True)
            item = resp.get("Item")
            if not item:
                return
            holders = [h for h in item.get("holders", []) if h.get("job_id") != job_id]
            with suppress(ddb.meta.client.exceptions.ConditionalCheckFailedException):
                await table.update_item(
                    Key={"pk": _PK, "sk": _SK},
                    UpdateExpression="SET current_count = :c, holders = :h",
                    ConditionExpression="current_count > :zero",
                    ExpressionAttributeValues={
                        ":c": max(0, int(item.get("current_count", 0)) - 1),
                        ":h": holders,
                        ":zero": 0,
                    },
                )

    async def cleanup_expired(self, ttl_seconds: int = 300) -> int:
        """Scan holders for acquired_at older than ttl_seconds, reclaim slots."""
        cutoff = datetime.now(tz=UTC).timestamp() - ttl_seconds
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            resp = await table.get_item(Key={"pk": _PK, "sk": _SK}, ConsistentRead=True)
            item = resp.get("Item")
            if not item:
                return 0
            active: list[dict[str, Any]] = []
            expired = 0
            for h in item.get("holders", []):
                try:
                    acquired_ts = datetime.fromisoformat(h["acquired_at"]).timestamp()
                except Exception:
                    active.append(h)
                    continue
                if acquired_ts >= cutoff:
                    active.append(h)
                else:
                    expired += 1
            if expired == 0:
                return 0
            await table.update_item(
                Key={"pk": _PK, "sk": _SK},
                UpdateExpression="SET current_count = :c, holders = :h",
                ExpressionAttributeValues={
                    ":c": max(0, int(item.get("current_count", 0)) - expired),
                    ":h": active,
                },
            )
            return expired

    @asynccontextmanager
    async def slot(self, job_id: str):
        """Context manager: acquire on enter, release on exit (even on error)."""
        await self.acquire(job_id)
        try:
            yield
        finally:
            await self.release(job_id)
