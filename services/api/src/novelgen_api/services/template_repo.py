"""Outline template repository."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class TemplateRepo:
    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy

    async def list_templates(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return await self._tenancy.query_by_sk_prefix(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            sk_prefix="OUTLINE_TEMPLATE#",
            limit=limit,
        )

    async def upsert(
        self,
        *,
        template_id: str,
        name: str,
        description: str,
        default_chapter_count: int,
        beats: list[dict[str, Any]],
        updated_by: str,
        updated_at: str,
    ) -> None:
        existing = await self._tenancy.get(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk=f"OUTLINE_TEMPLATE#{template_id}",
        )
        version = int(existing.get("version", 0)) + 1 if existing else 1
        await self._tenancy.put(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            item={
                "pk": "CONFIG",
                "sk": f"OUTLINE_TEMPLATE#{template_id}",
                "template_id": template_id,
                "name": name,
                "description": description,
                "default_chapter_count": default_chapter_count,
                "beats": json.dumps(beats),
                "version": version,
                "updated_by": updated_by,
                "updated_at": updated_at,
            },
        )

    async def delete(self, template_id: str) -> None:
        await self._tenancy.delete(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk=f"OUTLINE_TEMPLATE#{template_id}",
        )
