"""/api/v1/generations/{gid}/chapters/{n}/critique (U5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import Principal

from novelgen_api.services.critique_repo import get_critique

router = APIRouter(prefix="/api/v1/generations", tags=["critique"])


@router.get("/{gid}/chapters/{n}/critique")
async def read_critique(
    gid: UUID, n: int, principal: Principal = PrincipalDep
) -> dict:
    result = await get_critique(
        team_id=principal.team_id, generation_id=gid, chapter_idx=n
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "CRITIQUE_NOT_FOUND", "chapter": n}},
        )
    return result
