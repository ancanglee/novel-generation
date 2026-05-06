"""CancelCache tests."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from worker_generation.cancel_cache import CancelCache


@pytest.mark.asyncio
async def test_cache_hits_after_first_read():
    reader = AsyncMock()
    reader.is_canceled = AsyncMock(return_value=False)
    cache = CancelCache(reader)

    team, job = uuid4(), uuid4()
    await cache.is_canceled(team, job)
    await cache.is_canceled(team, job)
    await cache.is_canceled(team, job)

    assert reader.is_canceled.await_count == 1


@pytest.mark.asyncio
async def test_invalidate_forces_reread():
    reader = AsyncMock()
    reader.is_canceled = AsyncMock(side_effect=[False, True])
    cache = CancelCache(reader)
    team, job = uuid4(), uuid4()

    first = await cache.is_canceled(team, job)
    cache.invalidate(team, job)
    second = await cache.is_canceled(team, job)

    assert first is False
    assert second is True
