"""Tests for EMF metric formatting."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from worker_critic.metrics import (
    emit_duration_ms,
    emit_failure,
    emit_score_bucket,
    emit_total,
)


def _capture(func, *args, **kwargs) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    line = buf.getvalue().strip().splitlines()[-1]
    return json.loads(line)


def test_emit_duration_ms_emf_shape() -> None:
    obj = _capture(emit_duration_ms, 123.4, "dev")
    assert obj["CriticDurationMs"] == 123.4
    assert obj["Env"] == "dev"
    assert obj["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "novelgen/critic"


def test_emit_failure_includes_reason_dim() -> None:
    obj = _capture(emit_failure, "dev", "Throttling")
    assert obj["CriticFailureCount"] == 1.0
    assert obj["Reason"] == "Throttling"


def test_emit_total_unit_count() -> None:
    obj = _capture(emit_total, "dev")
    unit = obj["_aws"]["CloudWatchMetrics"][0]["Metrics"][0]["Unit"]
    assert unit == "Count"


def test_emit_score_bucket_boundaries() -> None:
    assert _capture(emit_score_bucket, 0, "dev")["Bucket"] == "0-40"
    assert _capture(emit_score_bucket, 39, "dev")["Bucket"] == "0-40"
    assert _capture(emit_score_bucket, 40, "dev")["Bucket"] == "40-70"
    assert _capture(emit_score_bucket, 69, "dev")["Bucket"] == "40-70"
    assert _capture(emit_score_bucket, 70, "dev")["Bucket"] == "70-90"
    assert _capture(emit_score_bucket, 89, "dev")["Bucket"] == "70-90"
    assert _capture(emit_score_bucket, 90, "dev")["Bucket"] == "90-100"
    assert _capture(emit_score_bucket, 100, "dev")["Bucket"] == "90-100"
