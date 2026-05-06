"""Observability adapter: structured logs + EMF metrics + helpers."""

from novelgen_obs.logger import get_logger, set_request_id
from novelgen_obs.metrics import (
    emit_bedrock_tokens,
    emit_cross_team_denied,
    emit_http_duration,
    emit_job_duration,
    emit_metric,
)

__all__ = [
    "emit_bedrock_tokens",
    "emit_cross_team_denied",
    "emit_http_duration",
    "emit_job_duration",
    "emit_metric",
    "get_logger",
    "set_request_id",
]
