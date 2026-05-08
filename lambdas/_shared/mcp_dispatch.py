"""Shared helpers for AgentCore Gateway MCP lambdas.

Event shape (AgentCore Gateway → Lambda):
    {
        "toolName": "remember",
        "arguments": {...},
        // Plus context fields like "session", "traceId" which we ignore here.
    }

Return value:
    {
        "content": [{"type": "text", "text": "..."} | {"type": "json", "data": {...}}],
        "isError": false
    }
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger("gateway_mcp")


def text_result(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def json_result(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def error_result(message: str) -> dict[str, Any]:
    return text_result(f"ERROR: {message}", is_error=True)


async def dispatch(
    event: dict[str, Any],
    handlers: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]],
) -> dict[str, Any]:
    """Route event.toolName to a handler. Missing tool → error response."""
    tool = event.get("toolName") or event.get("name")
    args = event.get("arguments") or {}
    if not tool or tool not in handlers:
        return error_result(f"unknown tool: {tool!r}")
    try:
        result = await handlers[tool](args)
    except KeyError as e:
        return error_result(f"missing argument: {e}")
    except Exception as e:  # noqa: BLE001
        log.exception("tool_handler_failed tool=%s", tool)
        return error_result(f"{type(e).__name__}: {e}")
    return result
