"""GET/PUT /admin/model-configs/{stage} with optimistic locking + atomic audit."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from novelgen_types.identity import Principal
from pydantic import BaseModel, Field

from novelgen_api.deps import tenancy_table
from novelgen_api.services.model_config_repo import ModelConfigRepo, OptimisticLockError

from ._deps import AdminPrincipalDep, make_audit_put_item, now_iso

router = APIRouter()

_TENANCY = os.environ.get("TENANCY_TABLE", "novelgen_tenancy")
_AUDIT = os.environ.get("AUDIT_EVENTS_TABLE", "novelgen_audit_events")

_VALID_STAGES = {
    "classification",
    "character",
    "map",
    "style",
    "outline",
    "chapter",
    "self_critique",
    "critic",
    "consistency",
}

_VALID_MODELS = {
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-sonnet-4-7",
    "claude-haiku-4-5",
}


class ModelEntryBody(BaseModel):
    model_id: str = Field(pattern="^claude-(opus|sonnet|haiku)-[0-9]+-[0-9]+$")
    max_output_tokens: int = Field(ge=1, le=8192)
    temperature: float = Field(ge=0.0, le=1.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class UpdateModelConfigBody(BaseModel):
    primary: ModelEntryBody
    fallback: ModelEntryBody | None = None
    expected_version: int = Field(ge=0)


def _repo() -> ModelConfigRepo:
    return ModelConfigRepo(tenancy_table(), audit_table_name=_AUDIT, tenancy_table_name=_TENANCY)


@router.get("/model-configs")
async def list_model_configs(principal: Principal = AdminPrincipalDep) -> dict:
    records = await _repo().list_all()
    return {
        "stages": [
            {
                "stage": r.stage,
                "primary": r.primary,
                "fallback": r.fallback,
                "version": r.version,
                "updated_by": r.updated_by,
                "updated_at": r.updated_at,
            }
            for r in records
        ]
    }


@router.get("/model-configs/{stage}")
async def get_model_config(stage: str, principal: Principal = AdminPrincipalDep) -> dict:
    if stage not in _VALID_STAGES:
        raise HTTPException(400, {"error": {"code": "INVALID_STAGE"}})
    record = await _repo().get(stage)
    if not record:
        raise HTTPException(404, {"error": {"code": "MODEL_CONFIG_NOT_FOUND"}})
    return {
        "stage": record.stage,
        "primary": record.primary,
        "fallback": record.fallback,
        "version": record.version,
        "updated_by": record.updated_by,
        "updated_at": record.updated_at,
    }


@router.put("/model-configs/{stage}")
async def put_model_config(
    stage: str,
    body: UpdateModelConfigBody,
    request: Request,
    principal: Principal = AdminPrincipalDep,
) -> dict:
    if stage not in _VALID_STAGES:
        raise HTTPException(400, {"error": {"code": "INVALID_STAGE"}})
    if body.primary.model_id not in _VALID_MODELS:
        raise HTTPException(400, {"error": {"code": "INVALID_MODEL_ID"}})

    existing = await _repo().get(stage)
    before: dict[str, Any] | None = None
    if existing:
        before = {
            "primary": existing.primary,
            "fallback": existing.fallback,
            "version": existing.version,
        }

    after = {
        "primary": body.primary.model_dump(),
        "fallback": body.fallback.model_dump() if body.fallback else None,
    }
    audit_item = make_audit_put_item(
        table_name=_AUDIT,
        actor=principal,
        action="admin.model_config.update",
        resource_type="model_config",
        resource_id=stage,
        details={"stage": stage, "before": before, "after": after},
        client_ip=request.client.host if request.client else None,
    )

    try:
        record = await _repo().put_with_audit(
            stage=stage,
            primary=body.primary.model_dump(),
            fallback=body.fallback.model_dump() if body.fallback else None,
            expected_version=body.expected_version,
            audit_item=audit_item,
            updated_by=str(principal.user_id),
            updated_at=now_iso(),
        )
    except OptimisticLockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "VERSION_CONFLICT",
                    "message": "模型配置已被他人更新，请刷新后重试",
                }
            },
        ) from exc

    return {
        "stage": record.stage,
        "version": record.version,
        "updated_by": record.updated_by,
        "updated_at": record.updated_at,
    }
