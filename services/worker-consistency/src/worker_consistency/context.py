"""Build ConsistencyAgent input context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ConsistencyContext:
    generation_id: UUID
    team_id: UUID
    scan_from: int
    scan_to: int
    chapters_text: dict[int, str]  # idx -> text
    memory_facts: list[dict[str, Any]]
    character_snapshots: list[dict[str, Any]]
    memory_unavailable: bool
    env: str
    request_id: str


def render_prompt(*, template: str, ctx: ConsistencyContext) -> str:
    chapters_joined = "\n\n".join(
        f"=== 第 {idx} 章 ===\n{text}"
        for idx, text in sorted(ctx.chapters_text.items())
    )
    replacements = {
        "{{scan_from}}": str(ctx.scan_from),
        "{{scan_to}}": str(ctx.scan_to),
        "{{memory_facts_json}}": json.dumps(ctx.memory_facts, ensure_ascii=False, indent=2),
        "{{character_snapshots_json}}": json.dumps(
            ctx.character_snapshots, ensure_ascii=False, indent=2
        ),
        "{{chapters_text}}": chapters_joined,
    }
    out = template
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out
