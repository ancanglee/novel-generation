"""Smoke tests for observability adapter."""

from __future__ import annotations

from novelgen_obs.logger import get_logger, set_request_id


def test_logger_factory_returns_powertools_logger() -> None:
    logger = get_logger("test-service")
    assert logger is not None


def test_set_request_id_does_not_raise() -> None:
    set_request_id("test-req-id")
    logger = get_logger("test-service")
    logger.info("hello")
