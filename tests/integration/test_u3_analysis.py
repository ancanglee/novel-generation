"""U3 integration smoke test: validate that every sub-agent's JSON schema is valid
and the Supervisor dispatches through a canned decision sequence without hitting AWS.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from worker_analysis.agents._bedrock import ToolCallResult
from worker_analysis.agents.chapter_all import _SCHEMA as CH_SCHEMA
from worker_analysis.checkpoint import CheckpointStore
from worker_analysis.supervisor import Supervisor, SupervisorContext


class _MemCheckpoint:
    async def save(self, **kwargs):  # type: ignore[no-untyped-def]
        pass

    async def load(self, *a, **kw):
        return None

    async def clear(self, *a, **kw):
        return None


def test_chapter_schema_has_required_sections():
    for key in ("character_updates", "map_updates", "events", "facts"):
        assert key in CH_SCHEMA["required"]


@pytest.mark.asyncio
async def test_supervisor_end_to_end_with_canned_decisions():
    """Simulate a tiny run: sample → classify → finalize."""
    dispatcher = AsyncMock(return_value={"ok": True})
    sup = Supervisor(dispatcher=dispatcher, checkpoint=_MemCheckpoint())  # type: ignore[arg-type]

    decisions = iter(
        [
            {"tool": "sample_chapters", "args": {"chapter_titles": ["C1"], "total_words": 100}, "reason": "start"},
            {"tool": "classify_tags", "args": {"chapter_indices": [1]}, "reason": "genre"},
            {"tool": "finalize_report", "args": {"done": True}, "reason": "fin"},
        ]
    )

    async def fake_invoke(**kwargs):
        return ToolCallResult(name="next_step", input=next(decisions), stop_reason="tool_use")

    with patch("worker_analysis.supervisor.invoke_tool", new=AsyncMock(side_effect=fake_invoke)):
        ctx = SupervisorContext(team_id=uuid4(), job_id=uuid4(), novel_id=uuid4(), chapter_count=1)
        result = await sup.run(ctx)

    assert result == {"done": True}
    assert dispatcher.await_count == 2
    assert ctx.step_history == ["sample_chapters", "classify_tags", "finalize_report"]
