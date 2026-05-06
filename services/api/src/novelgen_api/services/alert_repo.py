"""AlertRule repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class AlertRepo:
    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy

    async def list_rules(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return await self._tenancy.query_by_sk_prefix(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            sk_prefix="ALERT_RULE#",
            limit=limit,
        )

    async def upsert(
        self,
        *,
        rule_id: str,
        metric: str,
        threshold: float,
        comparison: str,
        window_minutes: int,
        severity: str,
        enabled: bool,
        updated_by: str,
        updated_at: str,
    ) -> None:
        await self._tenancy.put(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            item={
                "pk": "CONFIG",
                "sk": f"ALERT_RULE#{rule_id}",
                "rule_id": rule_id,
                "metric": metric,
                "threshold": threshold,
                "comparison": comparison,
                "window_minutes": window_minutes,
                "severity": severity,
                "enabled": enabled,
                "updated_by": updated_by,
                "updated_at": updated_at,
            },
        )

    async def delete(self, rule_id: str) -> None:
        await self._tenancy.delete(
            team_id=UUID("00000000-0000-0000-0000-000000000000"),
            pk="CONFIG",
            sk=f"ALERT_RULE#{rule_id}",
        )
