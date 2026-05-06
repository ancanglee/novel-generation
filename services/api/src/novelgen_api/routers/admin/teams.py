"""GET /admin/teams + admin mutations."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from novelgen_types.identity import Principal
from pydantic import BaseModel, Field

from novelgen_api.deps import tenancy_table
from novelgen_api.services.admin_team_repo import AdminTeamRepo

from ._deps import AdminPrincipalDep

router = APIRouter()


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/teams")
async def list_teams(principal: Principal = AdminPrincipalDep) -> dict:
    teams = await AdminTeamRepo(tenancy_table()).list_teams()
    return {"teams": teams, "count": len(teams)}


@router.get("/teams/{team_id}")
async def get_team(team_id: UUID, principal: Principal = AdminPrincipalDep) -> dict:
    team = await AdminTeamRepo(tenancy_table()).get_team(team_id)
    if not team:
        from fastapi import HTTPException

        raise HTTPException(404, {"error": {"code": "TEAM_NOT_FOUND"}})
    return team


@router.post("/teams/{team_id}/disable")
async def disable_team(team_id: UUID, principal: Principal = AdminPrincipalDep) -> dict:
    await AdminTeamRepo(tenancy_table()).disable_team(team_id)
    return {"team_id": str(team_id), "status": "disabled"}


@router.post("/teams/{team_id}/rename")
async def rename_team(
    team_id: UUID, body: RenameBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await AdminTeamRepo(tenancy_table()).rename_team(team_id, body.name)
    return {"team_id": str(team_id), "name": body.name}
