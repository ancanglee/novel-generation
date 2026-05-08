"""Unit tests for GatewayMcpClient using httpx MockTransport."""

from __future__ import annotations

import httpx
import pytest

from novelgen_agentcore_gateway import GatewayAuthError, GatewayMcpClient, GatewayToolError


@pytest.mark.asyncio
async def test_invoke_tool_success(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        payload = request.read().decode()
        assert '"tools/call"' in payload
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "x",
                "result": {"content": [{"type": "text", "text": "ok"}]},
            },
        )

    transport = httpx.MockTransport(handler)
    client = GatewayMcpClient(
        gateway_endpoint="https://gw.example/", token_provider=lambda: "tok"
    )
    async with client as c:
        # Replace the real client with one backed by MockTransport
        c._client = httpx.AsyncClient(transport=transport, timeout=5)
        res = await c.invoke_tool("remember", {"a": 1})
    assert res.text() == "ok"


@pytest.mark.asyncio
async def test_invoke_tool_auth_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="no creds")

    transport = httpx.MockTransport(handler)
    client = GatewayMcpClient(
        gateway_endpoint="https://gw.example/", token_provider=lambda: "tok"
    )
    async with client as c:
        c._client = httpx.AsyncClient(transport=transport, timeout=5)
        with pytest.raises(GatewayAuthError):
            await c.invoke_tool("x", {})


@pytest.mark.asyncio
async def test_invoke_tool_mcp_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "x",
                "error": {"code": -32000, "message": "boom"},
            },
        )

    transport = httpx.MockTransport(handler)
    client = GatewayMcpClient(
        gateway_endpoint="https://gw.example/", token_provider=lambda: "tok"
    )
    async with client as c:
        c._client = httpx.AsyncClient(transport=transport, timeout=5)
        with pytest.raises(GatewayToolError) as ei:
            await c.invoke_tool("x", {})
    assert ei.value.code == -32000
