"""/admin/audit list + detail with "audit the auditors" log (D4=C)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from novelgen_types.identity import Principal

from novelgen_api.deps import tenancy_table
from novelgen_api.services.audit_repo import AuditRepo

from ._deps import AdminPrincipalDep, Paginator

router = APIRouter()

# Side-channel logger that records which admin viewed which audit event.
_view_logger = logging.getLogger("novelgen.admin.audit_view")
_view_logger.setLevel(logging.INFO)


def _audit_repo() -> AuditRepo:
    # tenancy_table() happens to point at the same DDB table that stores AUDIT#
    # rows in V1 deployments; callers can override AUDIT_EVENTS_TABLE env.
    return AuditRepo(tenancy_table())


def _filter(items: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    team_id = kwargs.get("team_id")
    user_id = kwargs.get("user_id")
    action_contains = kwargs.get("action_contains")

    result: list[dict[str, Any]] = []
    for it in items:
        ts = it.get("timestamp")
        if date_from and ts and ts < date_from:
            continue
        if date_to and ts and ts > date_to:
            continue
        if team_id and str(it.get("team_id") or "") != team_id:
            continue
        if user_id and str(it.get("actor_user_id") or "") != user_id:
            continue
        if action_contains and action_contains not in (it.get("action") or ""):
            continue
        result.append(it)
    return result


@router.get("/audit")
async def list_audit_events(
    request: Request,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    action_contains: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = AdminPrincipalDep,
) -> dict:
    team_uuid: UUID | None
    try:
        team_uuid = UUID(team_id) if team_id else None
    except ValueError:
        raise HTTPException(400, {"error": {"code": "INVALID_TEAM_ID"}})

    rows = await _audit_repo().query(team_id=team_uuid, limit=500)
    filtered = _filter(
        rows,
        date_from=date_from,
        date_to=date_to,
        team_id=team_id,
        user_id=user_id,
        action_contains=action_contains,
    )
    page = Paginator.slice(filtered, page_size=limit, cursor=cursor)
    return {
        "items": page.items,
        "next_cursor": page.next_cursor,
        "count": len(page.items),
    }


@router.get("/audit/{event_id}")
async def get_audit_event(
    event_id: str,
    request: Request,
    team_id: str | None = Query(default=None),
    principal: Principal = AdminPrincipalDep,
) -> dict:
    team_uuid: UUID | None
    try:
        team_uuid = UUID(team_id) if team_id else None
    except ValueError:
        raise HTTPException(400, {"error": {"code": "INVALID_TEAM_ID"}})

    row = await _audit_repo().get_by_event_id(team_id=team_uuid, event_id=event_id)
    if not row:
        raise HTTPException(404, {"error": {"code": "AUDIT_EVENT_NOT_FOUND"}})

    # D4=C: we don't mask PII, but we audit the viewer.
    _view_logger.info(
        {
            "actor_user_id": str(principal.user_id),
            "actor_email": principal.email,
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "client_ip": request.client.host if request.client else "",
        }
    )
    return row
