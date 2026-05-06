"""/api/v1/conflicts/{conflict_id}/* (U5 Critic+Consistency conflict actions)."""

from __future__ import annotations

import os
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import Principal

from novelgen_api.services import conflict_repo
from novelgen_api.services.conflict_repo import ConflictFrozen, ConflictNotFound

router = APIRouter(prefix="/api/v1/conflicts", tags=["conflicts"])


class IgnoreResponse(BaseModel):
    conflict_id: UUID
    status: str


class RewriteResponse(BaseModel):
    conflict_id: UUID
    rewrite_attempts: int
    frozen: bool
    job_ref: str | None
    status: str


@router.post("/{conflict_id}/ignore", response_model=IgnoreResponse)
async def ignore_conflict(
    conflict_id: UUID, principal: Principal = PrincipalDep
) -> IgnoreResponse:
    try:
        item = await conflict_repo.find_by_id(
            team_id=principal.team_id, conflict_id=conflict_id
        )
    except ConflictNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CONFLICT_NOT_FOUND", "id": str(conflict_id)}},
        ) from exc

    generation_id = _extract_generation_id(item)
    await conflict_repo.ignore(
        team_id=principal.team_id,
        generation_id=generation_id,
        conflict_id=conflict_id,
    )
    return IgnoreResponse(conflict_id=conflict_id, status="ignored")


@router.post(
    "/{conflict_id}/rewrite",
    response_model=RewriteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def rewrite_conflict(
    conflict_id: UUID, principal: Principal = PrincipalDep
) -> RewriteResponse:
    max_attempts = int(os.environ.get("CONFLICT_REWRITE_MAX_ATTEMPTS", "3"))
    env = os.environ.get("NOVELGEN_ENV", "dev")

    try:
        item = await conflict_repo.find_by_id(
            team_id=principal.team_id, conflict_id=conflict_id
        )
    except ConflictNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CONFLICT_NOT_FOUND", "id": str(conflict_id)}},
        ) from exc

    generation_id = _extract_generation_id(item)
    chapter_idx = _extract_primary_chapter(item)
    summary = _extract_summary(item)

    try:
        attrs = await conflict_repo.request_rewrite(
            team_id=principal.team_id,
            generation_id=generation_id,
            conflict_id=conflict_id,
            max_attempts=max_attempts,
            env=env,
        )
    except ConflictFrozen as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT_REWRITE_FROZEN",
                    "message": "多次尝试未能解决，请手动编辑",
                    "id": str(conflict_id),
                }
            },
        ) from exc

    job_ref = await _invoke_u4_rewrite(
        generation_id=generation_id,
        chapter_idx=chapter_idx,
        instruction=summary,
        bearer=None,  # In-cluster call: api-service shares role with itself.
    )

    return RewriteResponse(
        conflict_id=conflict_id,
        rewrite_attempts=int(attrs.get("rewrite_attempts", 0)),
        frozen=bool(attrs.get("frozen", False)),
        job_ref=job_ref,
        status="rewrite_requested",
    )


# ----- helpers --------------------------------------------------------------


def _extract_generation_id(item: dict) -> UUID:
    sk = item.get("sk", "")
    # SK format: CONFLICT#{generation_id}#{conflict_id}
    parts = sk.split("#")
    if len(parts) < 3:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "MALFORMED_CONFLICT_SK"}},
        )
    try:
        return UUID(parts[1])
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "MALFORMED_CONFLICT_SK"}},
        ) from exc


def _extract_primary_chapter(item: dict) -> int:
    import json

    raw = item.get("conflict")
    blob = json.loads(raw) if isinstance(raw, str) else (raw or {})
    refs = blob.get("chapter_refs") or []
    if refs:
        try:
            return int(refs[0])
        except (TypeError, ValueError):
            pass
    return int(item.get("scan_to", 1))


def _extract_summary(item: dict) -> str:
    import json

    raw = item.get("conflict")
    blob = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return (blob.get("summary") or "")[:1800]


async def _invoke_u4_rewrite(
    *,
    generation_id: UUID,
    chapter_idx: int,
    instruction: str,
    bearer: str | None,
) -> str | None:
    """Call U4 rewrite endpoint in-process (same api-service container)."""
    base = os.environ.get("INTERNAL_API_BASE", "http://127.0.0.1:8000")
    url = f"{base}/api/v1/generations/{generation_id}/chapters/{chapter_idx}/rewrite"
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json={"instruction": instruction})
        if resp.status_code >= 300:
            return None
        data = resp.json()
        return str(data.get("generation_id") or "")
    except Exception:  # noqa: BLE001
        return None
