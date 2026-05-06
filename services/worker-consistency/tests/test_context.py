"""Tests for ConsistencyContext rendering."""

from __future__ import annotations

from uuid import uuid4

from worker_consistency.context import ConsistencyContext, render_prompt


def test_render_prompt_substitutes_and_sorts_chapters() -> None:
    ctx = ConsistencyContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=1,
        scan_to=3,
        chapters_text={3: "C3", 1: "C1", 2: "C2"},
        memory_facts=[{"k": "v"}],
        character_snapshots=[{"character_id": "abc"}],
        memory_unavailable=False,
        env="dev",
        request_id="r",
    )
    template = (
        "from={{scan_from}} to={{scan_to}}\n"
        "facts={{memory_facts_json}}\n"
        "snaps={{character_snapshots_json}}\n"
        "text={{chapters_text}}"
    )
    out = render_prompt(template=template, ctx=ctx)
    assert "from=1 to=3" in out
    # chapters rendered in increasing idx order
    assert out.index("=== 第 1 章 ===") < out.index("=== 第 2 章 ===") < out.index(
        "=== 第 3 章 ==="
    )


def test_render_prompt_empty_chapters() -> None:
    ctx = ConsistencyContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        scan_from=5,
        scan_to=10,
        chapters_text={},
        memory_facts=[],
        character_snapshots=[],
        memory_unavailable=True,
        env="dev",
        request_id="r",
    )
    out = render_prompt(template="{{chapters_text}}", ctx=ctx)
    assert out == ""
