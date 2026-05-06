"""CloudWatch EMF metric emitters (namespace = novelgen/critic, ConsistencyXxx)."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

_NAMESPACE = "novelgen/critic"


def _emit(metric_name: str, value: float, unit: str, dims: dict[str, str]) -> None:
    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
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
    _emit("ConsistencyDurationMs", ms, "Milliseconds", {"Env": env})


def emit_total(env: str) -> None:
    _emit("ConsistencyTotalCount", 1.0, "Count", {"Env": env})


def emit_failure(env: str, reason: str) -> None:
    _emit("ConsistencyFailureCount", 1.0, "Count", {"Env": env, "Reason": reason})


def emit_conflict(env: str, conflict_type: str) -> None:
    _emit(
        "ConsistencyConflictCount",
        1.0,
        "Count",
        {"Env": env, "Type": conflict_type},
    )


def emit_memory_unavailable(env: str) -> None:
    _emit("ConsistencyMemoryUnavailable", 1.0, "Count", {"Env": env})
