"""SelfCritiqueAgent — Layer-1 critique of a generated chapter."""

from __future__ import annotations

from typing import Any

from worker_generation.agents._bedrock_stream import invoke_tool
from worker_generation.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "category": {
                        "type": "string",
                        "enum": ["logic", "character", "style_drift", "consistency", "language"],
                    },
                    "excerpt": {"type": "string", "maxLength": 500},
                    "comment": {"type": "string", "maxLength": 500},
                },
                "required": ["severity", "category", "comment"],
            },
        },
        "suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "dimensions": {
            "type": "object",
            "properties": {
                "tone": {"type": "integer"},
                "pace": {"type": "integer"},
                "detail_density": {"type": "integer"},
                "dialogue_ratio": {"type": "integer"},
                "emotion_intensity": {"type": "integer"},
                "scope": {"type": "integer"},
            },
        },
    },
    "required": ["score", "issues", "suggestions", "dimensions"],
}


async def self_critique_chapter(
    chapter_text: str,
    target_style_vector_text: str,
    outline_item_summary: str,
    memory_facts: list[str],
    *,
    model_id: str = "anthropic.claude-sonnet-4-6-v1:0",
) -> dict[str, Any]:
    system = load_prompt("self_critique")
    memory_block = "\n".join(f"- {f}" for f in memory_facts[:20])
    user = (
        f"Target style vector:\n{target_style_vector_text}\n\n"
        f"Chapter outline summary:\n{outline_item_summary}\n\n"
        f"Memory context:\n{memory_block}\n\n"
        f"Generated chapter text:\n{chapter_text[:60000]}"
    )
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=user,
        tool_name="record_critique",
        tool_schema=_SCHEMA,
        stage="self_critique",
        max_tokens=3000,
    )
    return result.input
