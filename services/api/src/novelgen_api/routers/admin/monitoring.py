"""/admin/monitoring/summary — CloudWatch aggregation with minute-bucket TTLCache."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from novelgen_types.identity import Principal

from novelgen_api.services.cloudwatch_aggregator import (
    CloudWatchAggregator,
    SummaryRequest,
)

from ._cache import cache_get, cache_set
from ._deps import AdminPrincipalDep

router = APIRouter()

_AGGREGATOR = CloudWatchAggregator()


def _parse_dt(raw: str) -> datetime:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, {"error": {"code": "INVALID_DATETIME"}}) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/monitoring/summary")
async def get_monitoring_summary(
    from_: str = Query(alias="from"),
    to: str = Query(),
    principal: Principal = AdminPrincipalDep,
) -> dict:
    f = _parse_dt(from_)
    t = _parse_dt(to)
    if t <= f:
        raise HTTPException(400, {"error": {"code": "INVALID_RANGE"}})

    cached = cache_get(f, t)
    if cached is not None:
        return {**cached, "cache_hit": True}

    try:
        summary = await _AGGREGATOR.fetch_summary(SummaryRequest(from_=f, to=t))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            503,
            {
                "error": {
                    "code": "MONITORING_UNAVAILABLE",
                    "message": "监控聚合暂不可用",
                    "partial": True,
                }
            },
        ) from exc

    cache_set(f, t, summary)
    return {**summary, "cache_hit": False}
