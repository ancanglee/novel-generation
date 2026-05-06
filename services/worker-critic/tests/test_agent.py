"""Tests for CriticAgent: tool extraction + minimal report."""

from __future__ import annotations

from uuid import uuid4

import pytest
from worker_critic.agent import CriticAgent, CriticAgentError, minimal_failure_report
from worker_critic.context import CriticContext


def _ctx(idx: int = 1) -> CriticContext:
    return CriticContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        chapter_idx=idx,
        chapter_text="chapter body",
        layer1_critique={"ok": True},
        recent_summaries=[],
        style_vector={"tone": "calm"},
        env="dev",
        request_id="r",
    )


def test_extract_tool_input_from_converse_response() -> None:
    agent = CriticAgent()
    resp = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "t1",
                            "name": "emit_critique_report",
                            "input": {
                                "score": 85,
                                "summary": "ok",
                                "layer2_issues": [],
                            },
                        }
                    }
                ],
            }
        }
    }
    out = agent._extract_tool_input(resp)
    assert out["score"] == 85


def test_extract_tool_input_missing_tool_use_raises() -> None:
    agent = CriticAgent()
    resp = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "I refuse."}],
            }
        }
    }
    with pytest.raises(CriticAgentError):
        agent._extract_tool_input(resp)


def test_build_report_from_tool_input() -> None:
    agent = CriticAgent()
    ctx = _ctx(idx=7)
    report = agent._build_report(
        {
            "score": 77,
            "summary": "solid",
            "layer1_confirmed": ["A"],
            "layer1_overridden": [],
            "layer2_issues": [
                {
                    "severity": "warn",
                    "dimension": "style",
                    "message": "tone drifts",
                }
            ],
            "cross_chapter_concerns": [],
        },
        ctx,
    )
    assert report.score == 77
    assert report.chapter_idx == 7
    assert report.layer2_issues[0].dimension.value == "style"
    assert report.minimal is False


def test_minimal_failure_report_has_flag_and_reason() -> None:
    ctx = _ctx()
    r = minimal_failure_report(ctx, "bedrock throttled")
    assert r.minimal is True
    assert r.score == 0
    assert "critic_failed" in r.summary
