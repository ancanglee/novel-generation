"""Gateway MCP client for agent tool invocation.

AgentCore Gateway exposes tools over MCP (Model Context Protocol). We implement
the minimal `tools/call` JSON-RPC POST over HTTPS (not the SSE streaming variant),
which is sufficient for Lambda-backed targets.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class GatewayAuthError(Exception):
    """401/403 from Gateway — caller should invalidate token and retry once."""


class GatewayToolError(Exception):
    """Tool executed but returned an MCP error payload."""

    def __init__(self, tool: str, code: int, message: str) -> None:
        super().__init__(f"[{tool}] mcp error {code}: {message}")
        self.tool = tool
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ToolResult:
    content: list[dict[str, Any]]
    is_error: bool = False
    structured: dict[str, Any] | None = field(default=None)

    def text(self) -> str:
        """Concatenate all text content items into a single string."""
        parts: list[str] = []
        for item in self.content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)


class _TransientHttp(Exception):
    """Internal marker for tenacity retry."""


def _retryer() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type(_TransientHttp),
        reraise=True,
    )


class GatewayMcpClient:
    """HTTPS client that speaks MCP JSON-RPC to an AgentCore Gateway endpoint."""

    def __init__(
        self,
        *,
        gateway_endpoint: str,
        token_provider,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._endpoint = gateway_endpoint.rstrip("/")
        self._provider = token_provider  # callable () -> str (bearer)
        self._timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GatewayMcpClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def invoke_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """Invoke `tool_name` via MCP `tools/call`. Retries transient HTTP errors."""
        if self._client is None:
            raise RuntimeError("GatewayMcpClient used outside async context manager")

        body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        async for attempt in _retryer():
            with attempt:
                token = await _maybe_async(self._provider)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                try:
                    resp = await self._client.post(
                        self._endpoint, json=body, headers=headers
                    )
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                    raise _TransientHttp(str(e)) from e

                if resp.status_code in (401, 403):
                    raise GatewayAuthError(f"{resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 500:
                    raise _TransientHttp(f"{resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 400:
                    raise GatewayToolError(
                        tool_name, resp.status_code, resp.text[:500]
                    )

                data = resp.json()
                if "error" in data:
                    err = data["error"]
                    raise GatewayToolError(
                        tool_name, int(err.get("code", -1)), str(err.get("message", ""))
                    )
                result = data.get("result") or {}
                return ToolResult(
                    content=result.get("content") or [],
                    is_error=bool(result.get("isError", False)),
                    structured=result.get("structuredContent"),
                )
        raise RuntimeError("unreachable")  # pragma: no cover


async def _maybe_async(fn):
    """Call `fn()` which may be sync or async."""
    import inspect
    res = fn() if callable(fn) else fn
    if inspect.isawaitable(res):
        return await res
    return res
