"""Analysis Schema repository (admin-managed classification templates)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class SchemaRepo:
    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy

    async def list_schemas(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return await self._tenancy.query_by_sk_prefix(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            sk_prefix="ANALYSIS_SCHEMA#",
            limit=limit,
        )

    async def upsert(self, *, schema_id: str, name: str, fields: list[dict[str, Any]], updated_by: str, updated_at: str) -> None:
        existing = await self._tenancy.get(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk=f"ANALYSIS_SCHEMA#{schema_id}",
        )
        version = int(existing.get("version", 0)) + 1 if existing else 1
        await self._tenancy.put(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            item={
                "pk": "CONFIG",
                "sk": f"ANALYSIS_SCHEMA#{schema_id}",
                "schema_id": schema_id,
                "name": name,
                "fields": json.dumps(fields),
                "version": version,
                "updated_by": updated_by,
                "updated_at": updated_at,
            },
        )

    async def delete(self, schema_id: str) -> None:
        await self._tenancy.delete(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk=f"ANALYSIS_SCHEMA#{schema_id}",
        )
