"""Tests for style / memory / previous chapter block builders."""

from __future__ import annotations

from worker_generation.style_injection import (
    StyleVector,
    build_memory_block,
    build_previous_chapter_block,
    build_style_block,
    render_vector_prefix,
)


def _vec() -> StyleVector:
    return StyleVector(
        tone=70, pace=60, detail_density=50, dialogue_ratio=40,
        emotion_intensity=80, scope=55,
        explanations={"tone": "轻快幽默", "pace": "中速"},
    )


def test_vector_prefix_contains_all_dims():
    s = render_vector_prefix(_vec())
    for dim in ("tone", "pace", "detail_density", "dialogue_ratio", "emotion_intensity", "scope"):
        assert dim in s


def test_style_block_includes_refs():
    block = build_style_block(_vec(), ["ref1", "ref2", "ref3", "ref4"])
    assert "<style_reference>" in block
    assert "ref1" in block
    assert "ref3" in block
    # Only first 3 refs included
    assert "ref4" not in block


def test_style_block_handles_no_refs():
    block = build_style_block(_vec(), [])
    assert "无可用风格参考" in block


def test_memory_block_truncates_to_20():
    block = build_memory_block([f"fact-{i}" for i in range(50)])
    assert "fact-0" in block
    assert "fact-19" in block
    assert "fact-20" not in block


def test_previous_chapter_block_keeps_last_500_chars():
    # 使用不会出现在标签里的字符 "Z"，避免把 <previous_chapter_tail> 中的 a 字符计入。
    text = "Z" * 1000
    block = build_previous_chapter_block(text)
    assert block.count("Z") == 500
