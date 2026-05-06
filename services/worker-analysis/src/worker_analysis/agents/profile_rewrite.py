"""rewrite_character_profile — rare: used on identity reveal / missed protagonist (R4.4)."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.agents.character_global import _SCHEMA as CHARACTER_SCHEMA


async def rewrite_character_profile(
    character_id: str,
    display_name: str,
    history_summary: str,
    reason: str,
    *,
    model_id: str = "anthropic.claude-opus-4-7-v1:0",
) -> dict[str, Any]:
    system = (
        "You are rewriting a character's Profile because of a significant identity shift "
        "(e.g., undercover reveal, missed protagonist). Produce a single updated character block."
    )
    user = (
        f"Character ID: {character_id}\nDisplay name: {display_name}\n"
        f"Reason: {reason}\n\nFull history:\n{history_summary[:30000]}"
    )
    # Reuse the characters schema but expect exactly one entry
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=user,
        tool_name="record_characters",
        tool_schema=CHARACTER_SCHEMA,
        stage="rewrite_character_profile",
    )
    characters = result.input.get("characters", [])
    return characters[0] if characters else {}
