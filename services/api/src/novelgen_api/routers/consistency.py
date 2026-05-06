"""/api/v1/generations/{gid}/consistency-reports (U5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import Principal

from novelgen_api.services.consistency_repo import list_reports

router = APIRouter(prefix="/api/v1/generations", tags=["consistency"])


@router.get("/{gid}/consistency-reports")
async def read_consistency_reports(
    gid: UUID,
    since_chapter: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = PrincipalDep,
) -> dict:
    results = await list_reports(
        team_id=principal.team_id,
        generation_id=gid,
        since_chapter=since_chapter,
        limit=limit,
    )
    return {"reports": results, "count": len(results)}
