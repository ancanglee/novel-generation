"""extract_map_global — rough-read places, factions, and initial edges."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "places": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "place_type": {
                        "type": "string",
                        "enum": ["CITY", "COUNTRY", "SECT", "DOMAIN", "REALM", "BUILDING", "OTHER"],
                    },
                    "description": {"type": "string"},
                    "located_in": {"type": ["string", "null"]},
                },
                "required": ["place_id", "display_name"],
            },
        },
        "factions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "faction_id": {"type": "string"},
                    "display_name": {"type": "string"},
                    "faction_type": {
                        "type": "string",
                        "enum": ["SECT", "EMPIRE", "TRIBE", "CLAN", "ORGANIZATION", "OTHER"],
                    },
                    "alignment": {
                        "type": "string",
                        "enum": ["PROTAGONIST", "ANTAGONIST", "NEUTRAL", "UNKNOWN"],
                    },
                    "description": {"type": "string"},
                },
                "required": ["faction_id", "display_name"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "edge_type": {
                        "type": "string",
                        "enum": ["adjacent", "located_in", "belongs_to", "rival"],
                    },
                    "to": {"type": "string"},
                },
                "required": ["from", "edge_type", "to"],
            },
        },
    },
    "required": ["places", "factions", "edges"],
}


async def extract_map_global(
    samples_text: str,
    *,
    model_id: str = "anthropic.claude-sonnet-4-6-v1:0",
) -> dict[str, Any]:
    system = load_prompt("map_global")
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=f"Samples:\n{samples_text[:60000]}",
        tool_name="record_map",
        tool_schema=_SCHEMA,
        stage="extract_map_global",
    )
    return result.input
