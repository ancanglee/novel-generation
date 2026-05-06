"""/admin/alerts CRUD."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from novelgen_types.identity import Principal

from novelgen_api.deps import tenancy_table
from novelgen_api.services.alert_repo import AlertRepo

from ._deps import AdminPrincipalDep, now_iso

router = APIRouter()


class AlertRuleBody(BaseModel):
    rule_id: str = Field(min_length=1, max_length=64)
    metric: str = Field(min_length=1, max_length=100)
    threshold: float
    comparison: str = Field(pattern="^(gt|lt|gte|lte)$")
    window_minutes: int = Field(ge=1, le=60)
    severity: str = Field(pattern="^(warn|critical)$")
    enabled: bool = True


@router.get("/alerts")
async def list_alerts(principal: Principal = AdminPrincipalDep) -> dict:
    rows = await AlertRepo(tenancy_table()).list_rules()
    return {"alerts": rows, "count": len(rows)}


@router.put("/alerts/{rule_id}")
async def upsert_alert(
    rule_id: str, body: AlertRuleBody, principal: Principal = AdminPrincipalDep
) -> dict:
    await AlertRepo(tenancy_table()).upsert(
        rule_id=rule_id,
        metric=body.metric,
        threshold=body.threshold,
        comparison=body.comparison,
        window_minutes=body.window_minutes,
        severity=body.severity,
        enabled=body.enabled,
        updated_by=str(principal.user_id),
        updated_at=now_iso(),
    )
    return {"rule_id": rule_id, "status": "saved"}


@router.delete("/alerts/{rule_id}")
async def delete_alert(rule_id: str, principal: Principal = AdminPrincipalDep) -> dict:
    await AlertRepo(tenancy_table()).delete(rule_id)
    return {"rule_id": rule_id, "status": "deleted"}
