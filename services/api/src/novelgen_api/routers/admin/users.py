"""GET /admin/users + admin actions (disable / enable / reset / group)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from novelgen_types.identity import Principal

from novelgen_api.deps import tenancy_table
from novelgen_api.services.admin_user_repo import AdminUserRepo

from ._deps import AdminPrincipalDep

router = APIRouter()


class GroupBody(BaseModel):
    group: str


@router.get("/users")
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = AdminPrincipalDep,
) -> dict:
    repo = AdminUserRepo(tenancy_table())
    users = await repo.list_users(limit=limit)
    return {"users": users, "count": len(users)}


@router.post("/users/{user_id}/disable")
async def disable_user(user_id: UUID, principal: Principal = AdminPrincipalDep) -> dict:
    await AdminUserRepo(tenancy_table()).disable_user(user_id)
    return {"user_id": str(user_id), "status": "disabled"}


@router.post("/users/{user_id}/enable")
async def enable_user(user_id: UUID, principal: Principal = AdminPrincipalDep) -> dict:
    await AdminUserRepo(tenancy_table()).enable_user(user_id)
    return {"user_id": str(user_id), "status": "active"}


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: UUID, principal: Principal = AdminPrincipalDep) -> dict:
    await AdminUserRepo(tenancy_table()).reset_password(user_id)
    return {"user_id": str(user_id), "status": "reset_email_sent"}


@router.post("/users/{user_id}/groups/add")
async def add_group(
    user_id: UUID, body: GroupBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await AdminUserRepo(tenancy_table()).add_to_group(user_id, body.group)
    return {"user_id": str(user_id), "group": body.group, "status": "added"}


@router.post("/users/{user_id}/groups/remove")
async def remove_group(
    user_id: UUID, body: GroupBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await AdminUserRepo(tenancy_table()).remove_from_group(user_id, body.group)
    return {"user_id": str(user_id), "group": body.group, "status": "removed"}
