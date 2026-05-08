"""End-to-end smoke tests for AgentCore integration.

These tests require real AWS credentials and are **skipped by default**. Set
`AGENTCORE_E2E=1` in env + valid AGENTCORE_MEMORY_ID / AGENTCORE_WORKLOAD_NAME /
AGENTCORE_GATEWAY_URL to run.

Coverage:
- Memory write → read round-trip via AgentCoreMemoryClient
- Workload token acquire + cache hit
- Gateway tool `recall` via MCP client using workload token
- (Manual) Browser session start/stop (skipped unless CI opts in, because sessions
  cost real $).
"""

from __future__ import annotations

import os
import uuid
from uuid import UUID

import pytest

_ENABLED = os.environ.get("AGENTCORE_E2E") == "1"
pytestmark = pytest.mark.skipif(not _ENABLED, reason="AGENTCORE_E2E=1 required")


@pytest.fixture
def team_id() -> UUID:
    return UUID("00000000-0000-0000-0000-00000000ae00")


@pytest.fixture
def novel_id() -> UUID:
    return UUID("00000000-0000-0000-0000-00000000ae01")


@pytest.mark.asyncio
async def test_memory_roundtrip(team_id: UUID, novel_id: UUID):
    from worker_analysis.memory.agentcore_memory import (
        AgentCoreMemoryClient,
        MemoryItem,
    )

    client = AgentCoreMemoryClient()
    fact_key = f"test::{uuid.uuid4()}"
    items = [
        MemoryItem(
            fact_key=fact_key,
            fact_type="CHARACTER_SNAPSHOT",
            content={
                "character_id": "test-hero",
                "display_name": "测试主角",
                "chapter": 1,
                "attributes": {"level": 1},
            },
            source_chapter=1,
        )
    ]
    await client.put_batch(team_id, novel_id, items, session_id="test-session")

    records = await client.retrieve(
        team_id, novel_id, query="test-hero", top_k=5
    )
    assert any(fact_key in r.content_text for r in records), (
        "fact not found in RetrieveMemoryRecords"
    )


@pytest.mark.asyncio
async def test_workload_token_cache_hit():
    from novelgen_auth.workload_identity import WorkloadIdentityClient

    client = WorkloadIdentityClient()
    t1 = await client.get_token("gateway")
    t2 = await client.get_token("gateway")
    # Same access_token → served from cache
    assert t1.access_token == t2.access_token


@pytest.mark.asyncio
async def test_gateway_mcp_recall_roundtrip(team_id: UUID, novel_id: UUID):
    import os as _os

    from novelgen_agentcore_gateway import GatewayMcpClient
    from novelgen_auth.workload_identity import WorkloadIdentityClient

    gateway_url = _os.environ["AGENTCORE_GATEWAY_URL"]
    wid = WorkloadIdentityClient()

    async def _token() -> str:
        t = await wid.get_token("gateway")
        return t.access_token

    async with GatewayMcpClient(
        gateway_endpoint=gateway_url, token_provider=_token
    ) as gw:
        res = await gw.invoke_tool(
            "recall",
            {"team_id": str(team_id), "novel_id": str(novel_id), "query": "hero", "top_k": 3},
        )
    assert res.is_error is False
