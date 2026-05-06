"""Admin team management repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class AdminTeamRepo:
    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy

    async def list_teams(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return await self._tenancy.query_by_sk_prefix(
            team_id=None,  # type: ignore[arg-type]
            sk_prefix="TEAM_META#",
            limit=limit,
        ) if hasattr(self._tenancy, "scan_by_sk_prefix") else []

    async def get_team(self, team_id: UUID) -> dict[str, Any] | None:
        return await self._tenancy.get(
            team_id=team_id, pk=f"TEAM#{team_id}", sk=f"TEAM_META#{team_id}"
        )

    async def disable_team(self, team_id: UUID) -> None:
        await self._tenancy.update(
            team_id=team_id,
            pk=f"TEAM#{team_id}",
            sk=f"TEAM_META#{team_id}",
            update_expression="SET #s = :disabled",
            expression_names={"#s": "status"},
            expression_values={":disabled": "disabled"},
        )

    async def rename_team(self, team_id: UUID, new_name: str) -> None:
        await self._tenancy.update(
            team_id=team_id,
            pk=f"TEAM#{team_id}",
            sk=f"TEAM_META#{team_id}",
            update_expression="SET #n = :name",
            expression_names={"#n": "name"},
            expression_values={":name": new_name},
        )
