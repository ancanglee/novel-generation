"""Bedrock Converse Stream helper + shared Tool Use invoker (for non-streaming agents)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import aioboto3
from novelgen_obs import emit_metric, get_logger

log = get_logger("worker-generation.bedrock")


@dataclass(frozen=True)
class ToolCallResult:
    name: str
    input: dict[str, Any]


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
        "LlmInvocationCount", 1.0, dimensions={"Stage": stage or tool_name, "Model": model_id}
    )
    emit_metric(
        "BedrockTokensInput", float(usage.get("inputTokens", 0)),
        dimensions={"Stage": stage or tool_name, "Model": model_id},
    )
    emit_metric(
        "BedrockTokensOutput", float(usage.get("outputTokens", 0)),
        dimensions={"Stage": stage or tool_name, "Model": model_id},
    )
    for block in resp.get("output", {}).get("message", {}).get("content", []):
        if "toolUse" in block and block["toolUse"].get("name") == tool_name:
            return ToolCallResult(name=tool_name, input=block["toolUse"].get("input", {}))
    return ToolCallResult(name=tool_name, input={})


async def converse_stream(
    model_id: str,
    system_prompt: str,
    user_text: str,
    *,
    region: str = "us-east-1",
    max_tokens: int = 6000,
    temperature: float = 0.7,
) -> AsyncIterator[dict[str, Any]]:
    """Yield raw Bedrock stream events (text_delta / metadata / stop)."""
    session = aioboto3.Session()
    async with session.client("bedrock-runtime", region_name=region) as client:
        resp = await client.converse_stream(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        stream = resp.get("stream")
        async for event in stream:
            yield event
