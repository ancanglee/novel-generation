"""StyleInjectionBlock (F7=C): vector prefix + cached reference excerpts from GEN_CONTEXT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleVector:
    tone: int
    pace: int
    detail_density: int
    dialogue_ratio: int
    emotion_intensity: int
    scope: int
    explanations: dict[str, str]


def render_vector_prefix(v: StyleVector) -> str:
    """Render the 6-dim vector into a prompt-friendly block."""
    lines = [
        f"- 基调 (tone): {v.tone}/100 — {v.explanations.get('tone', '')}",
        f"- 节奏 (pace): {v.pace}/100 — {v.explanations.get('pace', '')}",
        f"- 描写密度 (detail_density): {v.detail_density}/100 — {v.explanations.get('detail_density', '')}",
        f"- 对话占比 (dialogue_ratio): {v.dialogue_ratio}/100 — {v.explanations.get('dialogue_ratio', '')}",
        f"- 情感强度 (emotion_intensity): {v.emotion_intensity}/100 — {v.explanations.get('emotion_intensity', '')}",
        f"- 世界观宏大度 (scope): {v.scope}/100 — {v.explanations.get('scope', '')}",
    ]
    return "\n".join(lines)


def build_style_block(v: StyleVector, reference_excerpts: list[str]) -> str:
    """Return the <style_reference> block to inject into the chapter prompt."""
    prefix = render_vector_prefix(v)
    refs = "\n\n---\n\n".join(reference_excerpts[:3]) if reference_excerpts else "(无可用风格参考)"
    return (
        "<style_reference>\n"
        f"## 6 维风格向量\n{prefix}\n\n"
        f"## 参考片段（学习写作技巧，不复用内容）\n{refs}\n"
        "</style_reference>"
    )


def build_memory_block(facts_text: list[str]) -> str:
    if not facts_text:
        return "<memory_context>\n(无既有事实可用；请基于当前章节大纲自洽生成)\n</memory_context>"
    body = "\n".join(f"- {t}" for t in facts_text[:20])
    return f"<memory_context>\n{body}\n</memory_context>"


def build_previous_chapter_block(tail_text: str) -> str:
    if not tail_text:
        return "<previous_chapter_tail>(这是第一章，无前章衔接)</previous_chapter_tail>"
    snippet = tail_text[-500:]
    return f"<previous_chapter_tail>\n{snippet}\n</previous_chapter_tail>"
