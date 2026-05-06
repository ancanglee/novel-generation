"""OutlineAgent — produces full-book outline via Opus 4.7 + Tool Use."""

from __future__ import annotations

from typing import Any

from worker_generation.agents._bedrock_stream import invoke_tool
from worker_generation.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "main_plot": {"type": "string", "maxLength": 2000},
        "world_summary": {"type": "string", "maxLength": 1500},
        "character_table": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string"},
                    "arc": {"type": "string"},
                },
                "required": ["id", "role"],
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter_idx": {"type": "integer", "minimum": 1},
                    "title": {"type": "string"},
                    "summary": {"type": "string", "maxLength": 500},
                    "main_characters": {"type": "array", "items": {"type": "string"}},
                    "locations": {"type": "array", "items": {"type": "string"}},
                    "plot_tags": {"type": "array", "items": {"type": "string"}},
                    "target_words": {"type": "integer", "minimum": 500},
                },
                "required": ["chapter_idx", "title", "summary", "target_words"],
            },
        },
    },
    "required": ["main_plot", "world_summary", "character_table", "items"],
}


async def generate_outline(
    analysis_report_text: str,
    mode: str,
    style_vector_text: str,
    target_chapter_count: int,
    target_words_per_chapter: int,
    *,
    model_id: str = "anthropic.claude-opus-4-7-v1:0",
) -> dict[str, Any]:
    system = load_prompt("outline")
    user = (
        f"Mode: {mode}\n"
        f"Target chapters: {target_chapter_count}, Target words/chapter: {target_words_per_chapter}\n\n"
        f"Style vector:\n{style_vector_text}\n\n"
        f"Source analysis report (may be truncated):\n{analysis_report_text[:40000]}"
    )
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=user,
        tool_name="record_outline",
        tool_schema=_SCHEMA,
        stage="outline",
        max_tokens=8000,
    )
    return result.input
