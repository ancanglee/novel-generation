"""OutlineReviewAgent (F3=B) — advisory review of user-edited outline."""

from __future__ import annotations

import json
from typing import Any

from worker_generation.agents._bedrock_stream import invoke_tool
from worker_generation.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "advice": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_idx": {"type": "integer"},
                    "concerns": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                    "severity": {"type": "string", "enum": ["info", "warn"]},
                },
                "required": ["item_idx", "severity"],
            },
        }
    },
    "required": ["advice"],
}


async def review_outline_changes(
    outline_old: dict[str, Any],
    outline_new: dict[str, Any],
    style_vector_text: str,
    *,
    model_id: str = "anthropic.claude-sonnet-4-6-v1:0",
) -> list[dict[str, Any]]:
    system = load_prompt("outline_review")
    user = (
        f"Style vector:\n{style_vector_text}\n\n"
        f"Original outline:\n{json.dumps(outline_old, ensure_ascii=False)[:20000]}\n\n"
        f"User-edited outline:\n{json.dumps(outline_new, ensure_ascii=False)[:20000]}"
    )
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=user,
        tool_name="record_advice",
        tool_schema=_SCHEMA,
        stage="outline_review",
        max_tokens=2500,
    )
    return result.input.get("advice", [])
