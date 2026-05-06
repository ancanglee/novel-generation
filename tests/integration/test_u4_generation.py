"""U4 integration smoke: style injection, schema validity, worker routing shape."""

from __future__ import annotations

from worker_generation.agents.outline import _SCHEMA as OUTLINE_SCHEMA
from worker_generation.agents.self_critique import _SCHEMA as CRIT_SCHEMA
from worker_generation.mode import Mode, prompt_name_for
from worker_generation.prompts import load_prompt
from worker_generation.style_injection import (
    StyleVector,
    build_memory_block,
    build_previous_chapter_block,
    build_style_block,
)


def test_mode_prompts_are_loadable():
    for mode in Mode:
        text = load_prompt(prompt_name_for(mode))
        assert len(text) > 100


def test_style_block_always_present():
    v = StyleVector(
        tone=70, pace=60, detail_density=50, dialogue_ratio=40,
        emotion_intensity=80, scope=55, explanations={},
    )
    block = build_style_block(v, ["ref1", "ref2"])
    assert "<style_reference>" in block
    assert "ref1" in block


def test_memory_block_handles_empty():
    assert "<memory_context>" in build_memory_block([])


def test_previous_chapter_first_chapter_message():
    assert "第一章" in build_previous_chapter_block("")


def test_outline_and_critique_schemas_have_required_blocks():
    assert "items" in OUTLINE_SCHEMA["properties"]
    assert "issues" in CRIT_SCHEMA["properties"]
    assert CRIT_SCHEMA["properties"]["score"]["maximum"] == 100
