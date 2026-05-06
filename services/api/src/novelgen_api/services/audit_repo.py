"""AuditEvent repository (read-side).

Writes happen only via TransactWriteItems embedded in admin mutation endpoints
(see `routers/admin/_deps.py::make_audit_put_item`). Direct PutItem is not
offered here to enforce the "business + audit atomic" invariant.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter


class AuditRepo:
    def __init__(self, audit_table: DynamoDBAdapter) -> None:
        self._audit = audit_table

    async def query(
        self,
        *,
        team_id: UUID | None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return most recent audit events for the given team (or GLOBAL)."""
        if team_id is None:
            pk_sentinel = UUID("00000000-0000-0000-0000-000000000000")
            rows = await self._audit.query_by_sk_prefix(
                team_id=pk_sentinel, sk_prefix="AUDIT#", limit=limit,
            )
        else:
            rows = await self._audit.query_by_sk_prefix(
                team_id=team_id, sk_prefix="AUDIT#", limit=limit,
            )
        return [self._unpack(r) for r in rows]

    async def get_by_event_id(
        self, *, team_id: UUID | None, event_id: str
    ) -> dict[str, Any] | None:
        """Scan AUDIT# rows and match embedded event_id (limited cardinality)."""
        rows = await self.query(team_id=team_id, limit=500)
        for r in rows:
            if r.get("event_id") == event_id:
                return r
        return None

    @staticmethod
    def _unpack(item: dict[str, Any]) -> dict[str, Any]:
        raw = item.get("details")
        if isinstance(raw, str):
            try:
                details = json.loads(raw)
            except Exception:
                details = {}
        elif isinstance(raw, dict):
            details = raw
        else:
            details = {}
        return {
            "event_id": item.get("event_id"),
            "timestamp": item.get("timestamp"),
            "actor_user_id": item.get("actor_user_id"),
            "actor_email": item.get("actor_email"),
            "action": item.get("action"),
            "resource_type": item.get("resource_type"),
            "resource_id": item.get("resource_id"),
            "team_id": item.get("team_id"),
            "client_ip": item.get("client_ip"),
            "details": details,
        }
