"""Structured JSON logger with request_id propagation via contextvar."""

from __future__ import annotations

from contextvars import ContextVar

from aws_lambda_powertools import Logger

_request_id: ContextVar[str] = ContextVar("novelgen_request_id", default="")


def set_request_id(request_id: str) -> None:
    """Set per-request id on the async contextvar."""
    _request_id.set(request_id)


def _inject_request_id(*, service: str, message: dict[str, object]) -> dict[str, object]:
    rid = _request_id.get()
    if rid:
        message["request_id"] = rid
    return message


def get_logger(service: str) -> Logger:
    """Return a powertools Logger for the given service name."""
    logger = Logger(
        service=service,
        use_rfc3339=True,
        json_default=str,
    )
    logger.append_keys(service=service)
    logger.register_processor(_inject_request_id)
    return logger
