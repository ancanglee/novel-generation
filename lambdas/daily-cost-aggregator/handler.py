"""Daily cost aggregator Lambda.

Pulls Bedrock token usage from CloudWatch (namespace NovelGen) for the prior day,
aggregates per Team × Model × Stage, and writes a compact row to novelgen_*_config
under `AGGREGATE#YYYYMMDD#{team}` for fast admin dashboards (NFR-D9=D).
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3

CONFIG_TABLE = os.environ["CONFIG_TABLE"]
ENV = os.environ.get("ENV", "dev")
NAMESPACE = "NovelGen"

_cw = boto3.client("cloudwatch")
_ddb = boto3.resource("dynamodb")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    target_date = _resolve_target_date(event)
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    rows = _aggregate_tokens(start, end)
    table = _ddb.Table(CONFIG_TABLE)
    date_str = target_date.strftime("%Y%m%d")

    with table.batch_writer() as batch:
        for (team, model, stage), totals in rows.items():
            batch.put_item(
                Item={
                    "pk": "CONFIG",
                    "sk": f"AGGREGATE#{date_str}#{team}#{stage}#{model}",
                    "team_id": team,
                    "model": model,
                    "stage": stage,
                    "date": date_str,
                    "input_tokens": totals["input"],
                    "output_tokens": totals["output"],
                }
            )

    return {"date": date_str, "rows_written": len(rows)}


def _resolve_target_date(event: dict[str, Any]):
    override = event.get("date") if event else None
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return (datetime.now(tz=UTC) - timedelta(days=1)).date()


def _aggregate_tokens(start: datetime, end: datetime) -> dict[tuple[str, str, str], dict[str, int]]:
    metrics: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"input": 0, "output": 0}
    )

    for metric_name, bucket in [
        ("BedrockTokensInput", "input"),
        ("BedrockTokensOutput", "output"),
    ]:
        paginator = _cw.get_paginator("list_metrics")
        for page in paginator.paginate(Namespace=NAMESPACE, MetricName=metric_name):
            for m in page["Metrics"]:
                dims = {d["Name"]: d["Value"] for d in m.get("Dimensions", [])}
                team = dims.get("Team", "unknown")
                model = dims.get("Model", "unknown")
                stage = dims.get("Stage", "unknown")

                resp = _cw.get_metric_statistics(
                    Namespace=NAMESPACE,
                    MetricName=metric_name,
                    Dimensions=m["Dimensions"],
                    StartTime=start,
                    EndTime=end,
                    Period=86400,
                    Statistics=["Sum"],
                )
                total = sum(int(dp["Sum"]) for dp in resp.get("Datapoints", []))
                if total:
                    metrics[(team, model, stage)][bucket] += total

    return metrics
