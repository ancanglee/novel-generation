"""Concurrency configuration repository (AD6=F admin端)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class ConcurrencyRepo:
    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy

    async def get(self) -> dict[str, Any] | None:
        return await self._tenancy.get(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk="CONCURRENCY",
        )

    async def upsert(
        self,
        *,
        deep_read_default: int,
        deep_read_max: int,
        chapter_parallel_max: int,
        updated_by: str,
        updated_at: str,
    ) -> None:
        await self._tenancy.put(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            item={
                "pk": "CONFIG",
                "sk": "CONCURRENCY",
                "deep_read_default": deep_read_default,
                "deep_read_max": deep_read_max,
                "chapter_parallel_max": chapter_parallel_max,
                "updated_by": updated_by,
                "updated_at": updated_at,
            },
        )
