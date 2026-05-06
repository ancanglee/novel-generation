"""extract_chapter_all — single-call composite chapter extraction (F7=A)."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "character_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "character_id": {"type": "string"},
                    "chapter": {"type": "integer"},
                    "location": {"type": ["string", "null"]},
                    "power_level": {"type": ["string", "null"]},
                    "mood": {"type": ["string", "null"]},
                    "alive": {"type": "boolean"},
                    "relationships_delta": {"type": "object"},
                },
                "required": ["character_id", "chapter"],
            },
        },
        "map_updates": {
            "type": "object",
            "properties": {
                "places": {"type": "array"},
                "factions": {"type": "array"},
                "edges": {"type": "array"},
            },
            "required": ["places", "factions", "edges"],
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "chapter": {"type": "integer"},
                    "participants": {"type": "array", "items": {"type": "string"}},
                    "location": {"type": ["string", "null"]},
                    "importance": {"type": "number", "minimum": 0, "maximum": 1},
                    "event_type": {
                        "type": "string",
                        "enum": [
                            "BATTLE",
                            "BREAKTHROUGH",
                            "DEATH",
                            "MEETING",
                            "CEREMONY",
                            "TRAVEL",
                            "OTHER",
                        ],
                    },
                },
                "required": ["event_id", "summary", "chapter"],
            },
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact_key": {"type": "string"},
                    "fact_type": {"type": "string"},
                    "content": {"type": "object"},
                },
                "required": ["fact_key", "fact_type", "content"],
            },
        },
    },
    "required": ["character_updates", "map_updates", "events", "facts"],
}


async def extract_chapter_all(
    chapter_idx: int,
    chapter_title: str,
    chapter_text: str,
    *,
    known_characters: list[str] | None = None,
    known_places: list[str] | None = None,
    novel_tags: list[str] | None = None,
    model_id: str = "anthropic.claude-sonnet-4-7-v1:0",
) -> dict[str, Any]:
    system = load_prompt("chapter_extraction")
    user = system.format(
        chapter_idx=chapter_idx,
        chapter_title=chapter_title,
        chapter_text=chapter_text[:60000],
        known_characters=", ".join(known_characters or [])[:500],
        known_places=", ".join(known_places or [])[:500],
        novel_tags=", ".join(novel_tags or []),
    )
    result = await invoke_tool(
        model_id=model_id,
        system_prompt="Extract chapter structure into the record_chapter_extraction tool.",
        user_text=user,
        tool_name="record_chapter_extraction",
        tool_schema=_SCHEMA,
        stage="extract_chapter_all",
    )
    return result.input
