"""Build CriticAgent input context.

Assembles:
- chapter text (S3)
- Layer-1 critique (DDB)
- recent N chapter summaries (Outline.items[])  — D3=B decision
- style vector (Novel.analysis.style_vector)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CriticContext:
    generation_id: UUID
    team_id: UUID
    chapter_idx: int
    chapter_text: str
    layer1_critique: dict[str, Any]
    recent_summaries: list[dict[str, Any]]  # [{"chapter_idx": int, "summary": str}, ...]
    style_vector: dict[str, Any]
    env: str
    request_id: str


def _window(current: int, count: int) -> range:
    """Last N chapters strictly before `current` (clipped to >=1)."""
    start = max(1, current - count)
    return range(start, current)


def pick_recent_summaries(
    outline_items: list[dict[str, Any]],
    current_chapter: int,
    count: int,
) -> list[dict[str, Any]]:
    """Select summaries for chapters within [current-count, current-1]."""
    target = set(_window(current_chapter, count))
    picked = [
        {"chapter_idx": item.get("chapter_idx"), "summary": item.get("summary", "")}
        for item in outline_items
        if item.get("chapter_idx") in target
    ]
    picked.sort(key=lambda x: x["chapter_idx"])
    return picked


def render_prompt(
    *,
    template: str,
    ctx: CriticContext,
) -> str:
    """Substitute template placeholders. Uses plain str.replace to avoid format-string pitfalls."""
    replacements = {
        "{{chapter_idx}}": str(ctx.chapter_idx),
        "{{chapter_text}}": ctx.chapter_text,
        "{{layer1_critique_json}}": json.dumps(
            ctx.layer1_critique, ensure_ascii=False, indent=2
        ),
        "{{recent_summaries}}": json.dumps(
            ctx.recent_summaries, ensure_ascii=False, indent=2
        ),
        "{{style_vector_json}}": json.dumps(
            ctx.style_vector, ensure_ascii=False, indent=2
        ),
    }
    out = template
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out
