"""/admin/concurrency get/put (AD6=F admin-configurable concurrency)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novelgen_types.identity import Principal

from novelgen_api.deps import tenancy_table
from novelgen_api.services.concurrency_repo import ConcurrencyRepo

from ._deps import AdminPrincipalDep, now_iso

router = APIRouter()


class ConcurrencyBody(BaseModel):
    deep_read_default: int = Field(ge=1, le=64)
    deep_read_max: int = Field(ge=1, le=128)
    chapter_parallel_max: int = Field(ge=1, le=4)


@router.get("/concurrency")
async def get_concurrency(principal: Principal = AdminPrincipalDep) -> dict:
    row = await ConcurrencyRepo(tenancy_table()).get()
    if not row:
        return {
            "deep_read_default": 20,
            "deep_read_max": 32,
            "chapter_parallel_max": 1,
            "updated_by": None,
            "updated_at": None,
        }
    return row


@router.put("/concurrency")
async def put_concurrency(
    body: ConcurrencyBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await ConcurrencyRepo(tenancy_table()).upsert(
        deep_read_default=body.deep_read_default,
        deep_read_max=body.deep_read_max,
        chapter_parallel_max=body.chapter_parallel_max,
        updated_by=str(principal.user_id),
        updated_at=now_iso(),
    )
    return {"status": "saved", **body.model_dump()}
