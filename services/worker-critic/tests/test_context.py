"""Tests for CriticContext helpers."""

from __future__ import annotations

import json
from uuid import uuid4

from worker_critic.context import CriticContext, pick_recent_summaries, render_prompt


def test_pick_recent_summaries_happy_path() -> None:
    items = [
        {"chapter_idx": 1, "summary": "s1"},
        {"chapter_idx": 2, "summary": "s2"},
        {"chapter_idx": 3, "summary": "s3"},
        {"chapter_idx": 4, "summary": "s4"},
        {"chapter_idx": 5, "summary": "s5"},
        {"chapter_idx": 6, "summary": "s6"},
        {"chapter_idx": 7, "summary": "s7"},
    ]
    picked = pick_recent_summaries(items, current_chapter=7, count=5)
    assert [p["chapter_idx"] for p in picked] == [2, 3, 4, 5, 6]


def test_pick_recent_summaries_clips_below_one() -> None:
    items = [{"chapter_idx": i, "summary": f"s{i}"} for i in range(1, 4)]
    picked = pick_recent_summaries(items, current_chapter=2, count=5)
    assert [p["chapter_idx"] for p in picked] == [1]


def test_pick_recent_summaries_empty_items() -> None:
    assert pick_recent_summaries([], current_chapter=10, count=5) == []


def test_render_prompt_substitutes_all_placeholders() -> None:
    ctx = CriticContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        chapter_idx=3,
        chapter_text="CHAPTER_BODY",
        layer1_critique={"note": "foo"},
        recent_summaries=[{"chapter_idx": 1, "summary": "S1"}],
        style_vector={"tone": "calm"},
        env="dev",
        request_id="r1",
    )
    template = (
        "idx={{chapter_idx}}\n"
        "body={{chapter_text}}\n"
        "layer1={{layer1_critique_json}}\n"
        "summaries={{recent_summaries}}\n"
        "style={{style_vector_json}}"
    )
    out = render_prompt(template=template, ctx=ctx)
    assert "idx=3" in out
    assert "body=CHAPTER_BODY" in out
    assert '"note": "foo"' in out
    assert '"summary": "S1"' in out or '"summary":"S1"' in out
    assert '"tone": "calm"' in out


def test_render_prompt_no_placeholders_unchanged() -> None:
    ctx = CriticContext(
        generation_id=uuid4(),
        team_id=uuid4(),
        chapter_idx=1,
        chapter_text="x",
        layer1_critique={},
        recent_summaries=[],
        style_vector={},
        env="dev",
        request_id="r",
    )
    assert render_prompt(template="no placeholders", ctx=ctx) == "no placeholders"
