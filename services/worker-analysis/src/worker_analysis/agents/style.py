"""analyze_style — 6-dim style vector via LLM scoring."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.prompts import load_prompt

_DIMS = ("tone", "pace", "detail_density", "dialogue_ratio", "emotion_intensity", "scope")

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{d: {"type": "integer", "minimum": 0, "maximum": 100} for d in _DIMS},
        "explanations": {
            "type": "object",
            "properties": {d: {"type": "string", "maxLength": 200} for d in _DIMS},
        },
    },
    "required": list(_DIMS) + ["explanations"],
}


async def analyze_style(
    samples_text: str,
    *,
    model_id: str = "anthropic.claude-sonnet-4-7-v1:0",
) -> dict[str, Any]:
    system = load_prompt("style")
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=system,
        user_text=f"Samples:\n{samples_text[:60000]}",
        tool_name="record_style_vector",
        tool_schema=_SCHEMA,
        stage="analyze_style",
    )
    return result.input
