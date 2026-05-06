"""/admin/outline-templates CRUD."""

from __future__ import annotations

from fastapi import APIRouter
from novelgen_types.identity import Principal
from pydantic import BaseModel, Field

from novelgen_api.deps import tenancy_table
from novelgen_api.services.template_repo import TemplateRepo

from ._deps import AdminPrincipalDep, now_iso

router = APIRouter()


class Beat(BaseModel):
    chapter_idx: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=500)


class UpsertTemplateBody(BaseModel):
    template_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=1000)
    default_chapter_count: int = Field(ge=1, le=500)
    beats: list[Beat]


@router.get("/outline-templates")
async def list_templates(principal: Principal = AdminPrincipalDep) -> dict:
    rows = await TemplateRepo(tenancy_table()).list_templates()
    return {"templates": rows, "count": len(rows)}


@router.put("/outline-templates/{template_id}")
async def upsert_template(
    template_id: str, body: UpsertTemplateBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await TemplateRepo(tenancy_table()).upsert(
        template_id=template_id,
        name=body.name,
        description=body.description,
        default_chapter_count=body.default_chapter_count,
        beats=[b.model_dump() for b in body.beats],
        updated_by=str(principal.user_id),
        updated_at=now_iso(),
    )
    return {"template_id": template_id, "status": "saved"}


@router.delete("/outline-templates/{template_id}")
async def delete_template(
    template_id: str, principal: Principal = AdminPrincipalDep
) -> dict:
    await TemplateRepo(tenancy_table()).delete(template_id)
    return {"template_id": template_id, "status": "deleted"}
