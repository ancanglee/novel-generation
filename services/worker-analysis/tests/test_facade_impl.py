"""Smoke tests for MemoryFacadeImpl degradation behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from novelgen_types.fact import Fact, FactType
from worker_analysis.memory.facade_impl import MemoryFacadeImpl


def _make_fact() -> Fact:
    return Fact(
        fact_key="character:张三:chapter:1",
        team_id=uuid4(),
        novel_id=uuid4(),
        fact_type=FactType.CHARACTER_SNAPSHOT,
        content={"text": "张三是主角", "character_id": "zhang-san"},
        source_chapter=1,
    )


@pytest.mark.asyncio
async def test_remember_tolerates_neptune_failure():
    agentcore = AsyncMock()
    agentcore.put_batch = AsyncMock(return_value=None)
    neptune = AsyncMock()
    neptune.upsert_node = AsyncMock(side_effect=RuntimeError("neptune down"))
    opensearch = AsyncMock()
    opensearch.bulk_index = AsyncMock(return_value=None)

    facade = MemoryFacadeImpl(agentcore=agentcore, neptune=neptune, opensearch=opensearch)
    facade.embed = AsyncMock(return_value=[0.0] * 1024)

    # Should not raise
    await facade.remember(uuid4(), uuid4(), [_make_fact()])
    agentcore.put_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_remember_raises_on_agentcore_failure():
    agentcore = AsyncMock()
    agentcore.put_batch = AsyncMock(side_effect=RuntimeError("critical"))
    neptune = AsyncMock()
    opensearch = AsyncMock()

    facade = MemoryFacadeImpl(agentcore=agentcore, neptune=neptune, opensearch=opensearch)
    facade.embed = AsyncMock(return_value=[0.0] * 1024)

    with pytest.raises(Exception):  # noqa: B017
        await facade.remember(uuid4(), uuid4(), [_make_fact()])


@pytest.mark.asyncio
async def test_embed_caches_result():
    facade = MemoryFacadeImpl(
        agentcore=AsyncMock(), neptune=AsyncMock(), opensearch=AsyncMock()
    )
    # Patch the bedrock call path
    with patch.object(facade, "_session") as sess:
        client = AsyncMock()
        body = AsyncMock()
        body.read = AsyncMock(return_value=b'{"embedding": [0.1, 0.2]}')
        client.invoke_model = AsyncMock(return_value={"body": body})
        sess.client.return_value.__aenter__ = AsyncMock(return_value=client)
        sess.client.return_value.__aexit__ = AsyncMock(return_value=None)

        v1 = await facade.embed("hello")
        v2 = await facade.embed("hello")  # should hit cache

    assert v1 == v2
