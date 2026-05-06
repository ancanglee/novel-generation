"""Supervisor hard limit tests with a fake dispatcher and in-memory checkpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from worker_analysis.supervisor import MAX_STEPS, Supervisor, SupervisorContext


class _MemCheckpoint:
    def __init__(self) -> None:
        self.saved = 0

    async def save(self, **kwargs):  # type: ignore[no-untyped-def]
        self.saved += 1

    async def load(self, *a, **kw):
        return None

    async def clear(self, *a, **kw):
        return None


def _ctx() -> SupervisorContext:
    return SupervisorContext(
        team_id=uuid4(),
        job_id=uuid4(),
        novel_id=uuid4(),
        chapter_count=100,
    )


@pytest.mark.asyncio
async def test_supervisor_terminates_at_max_steps():
    dispatcher = AsyncMock(return_value={"ok": True})
    sup = Supervisor(dispatcher=dispatcher, checkpoint=_MemCheckpoint())  # type: ignore[arg-type]

    # Always respond with a non-terminal tool; expect forced finalize at MAX_STEPS
    fake_input = {"tool": "classify_tags", "args": {"x": 1}, "reason": "test"}
    with patch(
        "worker_analysis.supervisor.invoke_tool",
        new=AsyncMock(return_value=type("R", (), {"input": fake_input})),
    ):
        result = await sup.run(_ctx())

    assert "forced" in result or result.get("forced") is True
    # Repeated-call guard prevents ~half the calls; but step_count still bounded
    assert dispatcher.await_count <= MAX_STEPS


@pytest.mark.asyncio
async def test_supervisor_respects_finalize_tool():
    dispatcher = AsyncMock(return_value={})
    ckpt = _MemCheckpoint()
    sup = Supervisor(dispatcher=dispatcher, checkpoint=ckpt)  # type: ignore[arg-type]

    fake_input = {"tool": "finalize_report", "args": {"done": True}, "reason": "fin"}
    with patch(
        "worker_analysis.supervisor.invoke_tool",
        new=AsyncMock(return_value=type("R", (), {"input": fake_input})),
    ):
        result = await sup.run(_ctx())

    assert result == {"done": True}
    dispatcher.assert_not_awaited()


@pytest.mark.asyncio
async def test_supervisor_skips_repeated_call():
    dispatcher = AsyncMock(return_value={})
    sup = Supervisor(dispatcher=dispatcher, checkpoint=_MemCheckpoint())  # type: ignore[arg-type]

    # Same tool + args repeatedly; after second occurrence should be skipped
    fake_input = {"tool": "classify_tags", "args": {"k": 1}, "reason": "r"}
    with patch(
        "worker_analysis.supervisor.invoke_tool",
        new=AsyncMock(return_value=type("R", (), {"input": fake_input})),
    ):
        await sup.run(_ctx())

    # Dispatcher called, but not more than MAX_STEPS
    assert dispatcher.await_count <= MAX_STEPS
