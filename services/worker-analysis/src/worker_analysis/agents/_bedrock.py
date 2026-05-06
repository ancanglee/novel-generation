"""Shared Bedrock Converse Tool Use helper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import aioboto3

from novelgen_obs import emit_metric, get_logger

log = get_logger("worker-analysis.bedrock")


@dataclass(frozen=True)
class ToolCallResult:
    name: str
    input: dict[str, Any]
    stop_reason: str


async def invoke_tool(
    model_id: str,
    system_prompt: str,
    user_text: str,
    tool_name: str,
    tool_schema: dict[str, Any],
    *,
    region: str = "us-east-1",
    max_tokens: int = 4000,
    temperature: float = 0.0,
    stage: str = "",
) -> ToolCallResult:
    """Invoke Bedrock Converse with toolChoice forcing a specific tool (D6=B Tool Use)."""
    tool_config = {
        "tools": [
            {
                "toolSpec": {
                    "name": tool_name,
                    "description": f"Structured output for {tool_name}",
                    "inputSchema": {"json": tool_schema},
                }
            }
        ],
        "toolChoice": {"tool": {"name": tool_name}},
    }

    session = aioboto3.Session()
    async with session.client("bedrock-runtime", region_name=region) as client:
        resp = await client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            toolConfig=tool_config,
        )

    usage = resp.get("usage", {})
    emit_metric(
        "LlmInvocationCount",
        1.0,
        dimensions={"Stage": stage or tool_name, "Model": model_id},
    )
    emit_metric(
        "BedrockTokensInput",
        float(usage.get("inputTokens", 0)),
        dimensions={"Stage": stage or tool_name, "Model": model_id},
    )
    emit_metric(
        "BedrockTokensOutput",
        float(usage.get("outputTokens", 0)),
        dimensions={"Stage": stage or tool_name, "Model": model_id},
    )

    stop_reason = resp.get("stopReason", "")
    message = resp.get("output", {}).get("message", {})
    for block in message.get("content", []):
        if "toolUse" in block:
            tu = block["toolUse"]
            if tu.get("name") == tool_name:
                return ToolCallResult(name=tool_name, input=tu.get("input", {}), stop_reason=stop_reason)

    log.warning("tool response missing; falling back to empty input", extra={"stop_reason": stop_reason})
    return ToolCallResult(name=tool_name, input={}, stop_reason=stop_reason)
