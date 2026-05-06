"""CloudWatch EMF metric emitters (namespace = novelgen/critic)."""

from __future__ import annotations

import json
import sys
from typing import Any

_NAMESPACE = "novelgen/critic"


def _emit(metric_name: str, value: float, unit: str, dims: dict[str, str]) -> None:
    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(__import__("time").time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": _NAMESPACE,
                    "Dimensions": [list(dims.keys())] if dims else [[]],
                    "Metrics": [{"Name": metric_name, "Unit": unit}],
                }
            ],
        },
        metric_name: value,
        **dims,
    }
    sys.stdout.write(json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()


def emit_duration_ms(ms: float, env: str) -> None:
    _emit("CriticDurationMs", ms, "Milliseconds", {"Env": env})


def emit_failure(env: str, reason: str) -> None:
    _emit("CriticFailureCount", 1.0, "Count", {"Env": env, "Reason": reason})


def emit_total(env: str) -> None:
    _emit("CriticTotalCount", 1.0, "Count", {"Env": env})


def emit_score_bucket(score: int, env: str) -> None:
    bucket = "0-40" if score < 40 else "40-70" if score < 70 else "70-90" if score < 90 else "90-100"
    _emit("CriticScore", 1.0, "Count", {"Env": env, "Bucket": bucket})
