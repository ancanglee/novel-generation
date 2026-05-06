"""CloudWatch metric aggregator for /admin/monitoring/summary.

Uses boto3 sync client inside `run_in_executor` to avoid blocking the
FastAPI event loop, and caches per-minute buckets via `_cache` module.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3

_REGION = os.environ.get("AWS_REGION", "us-east-1")


@dataclass
class SummaryRequest:
    from_: datetime
    to: datetime


class CloudWatchAggregator:
    """Batch-fetch CloudWatch metrics and aggregate into a summary dict."""

    def __init__(self) -> None:
        self._cw = boto3.client("cloudwatch", region_name=_REGION)

    async def fetch_summary(self, req: SummaryRequest) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_sync, req)

    def _fetch_sync(self, req: SummaryRequest) -> dict[str, Any]:
        queries = self._build_queries()
        resp = self._cw.get_metric_data(
            MetricDataQueries=queries,
            StartTime=req.from_,
            EndTime=req.to,
            ScanBy="TimestampAscending",
        )
        return self._aggregate(resp, req)

    @staticmethod
    def _build_queries() -> list[dict[str, Any]]:
        stages = [
            ("chapter_p95", "novelgen/generation", "ChapterDurationMs", "p95"),
            ("critic_p95", "novelgen/critic", "CriticDurationMs", "p95"),
            ("consistency_p95", "novelgen/critic", "ConsistencyDurationMs", "p95"),
            ("ingestion_p95", "novelgen/ingestion", "IngestionDurationMs", "p95"),
            ("analysis_p95", "novelgen/analysis", "AnalysisDurationMs", "p95"),
            ("sse_ttft_p95", "novelgen/frontend", "SseTtftMs", "p95"),
            ("gen_started", "novelgen/generation", "GenerationStarted", "Sum"),
            ("gen_succeeded", "novelgen/generation", "GenerationSucceeded", "Sum"),
            ("gen_failed", "novelgen/generation", "GenerationFailed", "Sum"),
        ]
        queries = []
        for qid, ns, name, stat in stages:
            queries.append(
                {
                    "Id": qid,
                    "MetricStat": {
                        "Metric": {"Namespace": ns, "MetricName": name},
                        "Period": 300,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                }
            )
        return queries

    @staticmethod
    def _last(values: list[float]) -> float:
        return values[-1] if values else 0.0

    @staticmethod
    def _sum(values: list[float]) -> int:
        return int(sum(values))

    @classmethod
    def _aggregate(cls, resp: dict[str, Any], req: SummaryRequest) -> dict[str, Any]:
        by_id: dict[str, list[float]] = {}
        for series in resp.get("MetricDataResults", []):
            by_id[series.get("Id", "")] = series.get("Values", []) or []

        started = cls._sum(by_id.get("gen_started", []))
        succeeded = cls._sum(by_id.get("gen_succeeded", []))
        failed = cls._sum(by_id.get("gen_failed", []))
        error_rate = (failed / started * 100) if started else 0.0

        return {
            "period": {
                "from": req.from_.astimezone(UTC).isoformat(),
                "to": req.to.astimezone(UTC).isoformat(),
            },
            "totals": {
                "generations_started": started,
                "generations_succeeded": succeeded,
                "generations_failed": failed,
            },
            "latency": {
                "ingestion_p95_ms": int(cls._last(by_id.get("ingestion_p95", []))),
                "analysis_p95_ms": int(cls._last(by_id.get("analysis_p95", []))),
                "chapter_p95_ms": int(cls._last(by_id.get("chapter_p95", []))),
                "critic_p95_ms": int(cls._last(by_id.get("critic_p95", []))),
                "consistency_p95_ms": int(cls._last(by_id.get("consistency_p95", []))),
            },
            "sse_ttft_p95_ms": int(cls._last(by_id.get("sse_ttft_p95", []))),
            "error_rate_percent": round(error_rate, 2),
        }
