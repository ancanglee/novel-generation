"""Structured JSON logger with request_id propagation via contextvar."""

from __future__ import annotations

import logging
from contextvars import ContextVar

from aws_lambda_powertools import Logger

_request_id: ContextVar[str] = ContextVar("novelgen_request_id", default="")


def set_request_id(request_id: str) -> None:
    """Set per-request id on the async contextvar."""
    _request_id.set(request_id)


class _RequestIdFilter(logging.Filter):
    """Inject the current request_id from the contextvar into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = _request_id.get()
        if rid:
            record.request_id = rid
        return True


def get_logger(service: str) -> Logger:
    """Return a powertools Logger for the given service name."""
    logger = Logger(
        service=service,
        use_rfc3339=True,
        json_default=str,
    )
    logger.append_keys(service=service)
    logger.addFilter(_RequestIdFilter())
    return logger
