"""Unit tests for RuntimeClient.

We don't talk to AWS — tests stub the aioboto3 session with async context managers
returning fake clients. The goal is to validate retry wiring, idempotency search,
and stream parsing, not to test AWS itself.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from novelgen_agentcore_runtime import RuntimeClient
from novelgen_agentcore_runtime.client import _is_transient


def _async_ctx(return_value):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_ensure_runtime_returns_existing_when_name_matches():
    ctl = MagicMock()
    ctl.list_agent_runtimes = AsyncMock(
        return_value={
            "agentRuntimes": [
                {
                    "agentRuntimeName": "novelgen-dev-supervisor-understanding",
                    "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-west-2:1:agent-runtime/r1",
                    "agentRuntimeId": "r1",
                    "status": "READY",
                }
            ]
        }
    )
    client = RuntimeClient(region="us-west-2")
    client._session = MagicMock()
    client._session.client = MagicMock(return_value=_async_ctx(ctl))

    out = await client.ensure_runtime(
        name="novelgen-dev-supervisor-understanding",
        container_uri="123.dkr.ecr.us-west-2.amazonaws.com/x:latest",
        role_arn="arn:aws:iam::1:role/r",
    )
    assert out.runtime_id == "r1"
    ctl.list_agent_runtimes.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_runtime_creates_when_missing():
    ctl = MagicMock()
    ctl.list_agent_runtimes = AsyncMock(return_value={"agentRuntimes": []})
    ctl.create_agent_runtime = AsyncMock(
        return_value={
            "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-west-2:1:agent-runtime/r2",
            "agentRuntimeId": "r2",
            "status": "CREATING",
        }
    )
    client = RuntimeClient()
    client._session = MagicMock()
    client._session.client = MagicMock(return_value=_async_ctx(ctl))

    out = await client.ensure_runtime(
        name="novelgen-dev-x", container_uri="img", role_arn="role"
    )
    assert out.runtime_id == "r2"
    ctl.create_agent_runtime.assert_awaited()


def test_is_transient_classifies_throttling():
    class Fake(Exception):
        response = {"Error": {"Code": "ThrottlingException"}}

    assert _is_transient(Fake())


def test_is_transient_ignores_validation():
    class Fake(Exception):
        response = {"Error": {"Code": "ValidationException"}}

    assert not _is_transient(Fake())
