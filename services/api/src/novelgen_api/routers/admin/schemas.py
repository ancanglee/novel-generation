"""/admin/analysis-schemas CRUD."""

from __future__ import annotations

from fastapi import APIRouter
from novelgen_types.identity import Principal
from pydantic import BaseModel, Field

from novelgen_api.deps import tenancy_table
from novelgen_api.services.schema_repo import SchemaRepo

from ._deps import AdminPrincipalDep, now_iso

router = APIRouter()


class SchemaField(BaseModel):
    key: str
    label: str
    type: str = Field(pattern="^(text|number|enum|list)$")
    options: list[str] = []
    required: bool = False


class UpsertSchemaBody(BaseModel):
    schema_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    fields: list[SchemaField]


@router.get("/analysis-schemas")
async def list_schemas(principal: Principal = AdminPrincipalDep) -> dict:
    rows = await SchemaRepo(tenancy_table()).list_schemas()
    return {"schemas": rows, "count": len(rows)}


@router.put("/analysis-schemas/{schema_id}")
async def upsert_schema(
    schema_id: str, body: UpsertSchemaBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await SchemaRepo(tenancy_table()).upsert(
        schema_id=schema_id,
        name=body.name,
        fields=[f.model_dump() for f in body.fields],
        updated_by=str(principal.user_id),
        updated_at=now_iso(),
    )
    return {"schema_id": schema_id, "status": "saved"}


@router.delete("/analysis-schemas/{schema_id}")
async def delete_schema(schema_id: str, principal: Principal = AdminPrincipalDep) -> dict:
    await SchemaRepo(tenancy_table()).delete(schema_id)
    return {"schema_id": schema_id, "status": "deleted"}
