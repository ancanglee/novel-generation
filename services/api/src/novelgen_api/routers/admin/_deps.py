"""Admin router shared dependencies.

- `require_admin_role` — FastAPI dependency that enforces the N5=C single-layer
  RBAC gate (403 when principal.global_role != admin).
- `audit_write_item_factory` — Helper building a DDB Put item for AuditEvent,
  used by admin mutation endpoints in TransactWriteItems.
- `Paginator` — simple cursor-based paginator for list endpoints.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request, status

from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import GlobalRole, Principal


def require_admin_role(
    request: Request,
    principal: Principal = PrincipalDep,
) -> Principal:
    """Gate admin endpoints. Raises 403 if principal is not admin."""
    if principal.global_role != GlobalRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "需要 admin 权限",
                    "request_id": getattr(request.state, "request_id", ""),
                }
            },
        )
    return principal


AdminPrincipalDep = Depends(require_admin_role)


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def make_audit_put_item(
    *,
    table_name: str,
    actor: Principal,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any],
    team_id: UUID | None = None,
    client_ip: str | None = None,
) -> dict[str, Any]:
    """Build a TransactWriteItems `Put` entry for an AuditEvent row.

    Uses a ConditionExpression guarding against duplicate event_id so replays
    can't silently overwrite. Caller composes this with the business-side Put
    in a single transact_write_items call for atomic "business + audit".
    """
    event_id = str(uuid4())
    ts = now_iso()
    pk = f"TEAM#{team_id}" if team_id else "GLOBAL"
    sk = f"AUDIT#{ts}#{event_id}"
    item = {
        "pk": {"S": pk},
        "sk": {"S": sk},
        "event_id": {"S": event_id},
        "timestamp": {"S": ts},
        "actor_user_id": {"S": str(actor.user_id)},
        "actor_email": {"S": actor.email},
        "action": {"S": action},
        "resource_type": {"S": resource_type},
        "resource_id": {"S": resource_id},
        "team_id": {"S": str(team_id) if team_id else ""},
        "details": {"S": _json(details)},
    }
    if client_ip:
        item["client_ip"] = {"S": client_ip}
    return {
        "Put": {
            "TableName": table_name,
            "Item": item,
            "ConditionExpression": "attribute_not_exists(pk) AND attribute_not_exists(sk)",
        }
    }


def _json(data: Any) -> str:
    import json as _j

    return _j.dumps(data, ensure_ascii=False, default=str)


@dataclass
class PaginatedResult:
    items: list[dict[str, Any]]
    next_cursor: str | None


class Paginator:
    """Cursor-based paginator over DDB Query results."""

    @staticmethod
    def slice(items: list[dict[str, Any]], page_size: int, cursor: str | None) -> PaginatedResult:
        start = 0
        if cursor:
            try:
                start = int(cursor)
            except ValueError:
                start = 0
        chunk = items[start : start + page_size]
        next_cursor = str(start + page_size) if start + page_size < len(items) else None
        return PaginatedResult(items=chunk, next_cursor=next_cursor)


def now_ms() -> int:
    return int(time.time() * 1000)
