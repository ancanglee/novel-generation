"""extract_characters_global — rough-read Profile drafts (F4=A)."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "gender": {"type": "string", "enum": ["MALE", "FEMALE", "UNKNOWN", "OTHER"]},
                    "appearance": {"type": "string"},
                    "personality": {"type": "string"},
                    "key_behaviors": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "first_chapter": {"type": "integer"},
                    "last_chapter": {"type": "integer"},
                    "importance": {"type": "number", "minimum": 0, "maximum": 1},
                    "faction_id": {"type": ["string", "null"]},
                },
                "required": ["character_id", "display_name", "importance"],
            },
        }
    },
    "required": ["characters"],
}


async def extract_characters_global(
    samples_text: str,
    novel_tags: list[str] | None = None,
    *,
    model_id: str = "anthropic.claude-sonnet-4-6-v1:0",
) -> list[dict[str, Any]]:
    system = load_prompt("character_global")
    tags_hint = ", ".join(novel_tags or []) or "unknown"
    prompt = f"Novel tags: {tags_hint}\n\nSamples:\n{samples_text[:60000]}"
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=prompt,
        tool_name="record_characters",
        tool_schema=_SCHEMA,
        stage="extract_characters_global",
    )
    return [c for c in result.input.get("characters", []) if c.get("importance", 0) >= 0.3]
