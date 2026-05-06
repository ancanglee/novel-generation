"""classify_tags — multi-label genre classification with confidence."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.prompts import load_prompt

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                },
                "required": ["tag", "confidence"],
            },
        }
    },
    "required": ["tags"],
}


async def classify_tags(
    samples_text: str,
    *,
    model_id: str = "anthropic.claude-sonnet-4-6-v1:0",
) -> list[dict[str, Any]]:
    system = load_prompt("classification")
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=f"Samples:\n{samples_text[:60000]}",
        tool_name="record_tags",
        tool_schema=_SCHEMA,
        stage="classify_tags",
    )
    return result.input.get("tags", [])
