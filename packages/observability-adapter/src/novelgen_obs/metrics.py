"""CloudWatch EMF metric emission (D8=A: zero-cost metric publishing via logs).

Each call produces a single log line that CloudWatch Log Metric Filter extracts into
Custom Metrics under namespace `NovelGen`.
"""

from __future__ import annotations

from typing import Any

from aws_lambda_powertools.metrics import Metrics, MetricUnit

# Single shared Metrics instance per process (thread-safe; powertools handles flushing)
_metrics = Metrics(namespace="NovelGen")


def emit_metric(
    name: str,
    value: float,
    unit: MetricUnit = MetricUnit.Count,
    dimensions: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a single EMF metric. Dimensions become CloudWatch metric dimensions."""
    if dimensions:
        for key, val in dimensions.items():
            _metrics.add_dimension(name=key, value=val)
    if metadata:
        for key, val in metadata.items():
            _metrics.add_metadata(key=key, value=val)
    _metrics.add_metric(name=name, unit=unit, value=value)
    # Flush synchronously per call to get a stable log line; powertools also supports batch
    _metrics.flush_metrics()


def emit_bedrock_tokens(
    team_id: str,
    stage: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    dims = {"Team": team_id, "Stage": stage, "Model": model}
    if input_tokens:
        emit_metric("BedrockTokensInput", float(input_tokens), MetricUnit.Count, dims)
    if output_tokens:
        emit_metric("BedrockTokensOutput", float(output_tokens), MetricUnit.Count, dims)


def emit_http_duration(route: str, status: int, duration_ms: float) -> None:
    emit_metric(
        "HttpRequestDurationMs",
        duration_ms,
        MetricUnit.Milliseconds,
        {"Route": route, "Status": str(status)},
    )


def emit_job_duration(job_type: str, status: str, duration_ms: float) -> None:
    emit_metric(
        "JobDurationMs",
        duration_ms,
        MetricUnit.Milliseconds,
        {"JobType": job_type, "Status": status},
    )


def emit_cross_team_denied(team_id: str) -> None:
    emit_metric("CrossTeamDenied", 1.0, MetricUnit.Count, {"Team": team_id})
