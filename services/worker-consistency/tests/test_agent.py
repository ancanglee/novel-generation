"""Tests for ConsistencyAgent: tool extraction + assemble."""

from __future__ import annotations

from uuid import uuid4

import pytest
from novelgen_types.critique import ConflictType, UserAction
from worker_consistency.agent import (
    ConsistencyAgent,
    ConsistencyAgentError,
    minimal_failure_report,
)
from worker_consistency.context import ConsistencyContext


def _ctx(memory_unavailable: bool = False) -> ConsistencyContext:
    return ConsistencyContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=1,
        scan_to=10,
        chapters_text={i: f"body {i}" for i in range(1, 11)},
        memory_facts=[],
        character_snapshots=[],
        memory_unavailable=memory_unavailable,
        env="dev",
        request_id="r",
    )


def test_extract_conflicts_happy_path() -> None:
    agent = ConsistencyAgent()
    resp = {
        "output": {
            "message": {
                "content": [
                    {
                        "toolUse": {
                            "name": "emit_consistency_report",
                            "input": {
                                "conflicts": [
                                    {
                                        "type": "timeline",
                                        "chapter_refs": [3, 7],
                                        "summary": "x",
                                        "evidence": [],
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        }
    }
    conflicts = agent._extract_conflicts(resp)
    assert len(conflicts) == 1


def test_extract_conflicts_missing_tool_raises() -> None:
    agent = ConsistencyAgent()
    with pytest.raises(ConsistencyAgentError):
        agent._extract_conflicts({"output": {"message": {"content": []}}})


def test_assemble_report_and_conflicts() -> None:
    agent = ConsistencyAgent()
    ctx = _ctx()
    report, conflicts = agent._assemble(
        [
            {
                "type": "timeline",
                "chapter_refs": [3, 7],
                "summary": "季节不一致",
                "evidence": ["第3章: 下雪", "第7章: 短袖"],
            },
            {
                "type": "character_state",
                "chapter_refs": [5, 8],
                "summary": "角色状态矛盾",
            },
        ],
        ctx,
    )
    assert len(conflicts) == 2
    assert conflicts[0].type == ConflictType.TIMELINE
    assert conflicts[0].rewrite_attempts == 0
    assert conflicts[0].user_action == UserAction.OPEN
    assert report.scan_from == 1 and report.scan_to == 10
    assert set(report.conflict_ids) == {c.conflict_id for c in conflicts}
    assert report.memory_unavailable is False


def test_assemble_when_memory_unavailable_preserved() -> None:
    agent = ConsistencyAgent()
    ctx = _ctx(memory_unavailable=True)
    report, _ = agent._assemble([], ctx)
    assert report.memory_unavailable is True
    assert report.conflict_ids == []


def test_minimal_failure_report_shape() -> None:
    ctx = _ctx()
    r = minimal_failure_report(ctx)
    assert r.minimal is True
    assert r.conflict_ids == []
