"""Observability adapter: structured logs + EMF metrics + OTEL bootstrap."""

from novelgen_obs.logger import get_logger, set_request_id
from novelgen_obs.metrics import (
    emit_bedrock_tokens,
    emit_cross_team_denied,
    emit_http_duration,
    emit_job_duration,
    emit_metric,
)
from novelgen_obs.otel_bootstrap import init_observability

__all__ = [
    "emit_bedrock_tokens",
    "emit_cross_team_denied",
    "emit_http_duration",
    "emit_job_duration",
    "emit_metric",
    "get_logger",
    "init_observability",
    "set_request_id",
]
