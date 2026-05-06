"""CriticAgent — Opus 4.7 Layer-2 review via Bedrock Converse + Tool Use.

Tool Use enforces JSON schema compliance on Opus 4.7 output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aioboto3
from novelgen_types.critique import CritiqueReport
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .context import CriticContext, render_prompt

_TOOL_NAME = "emit_critique_report"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Emit the Layer-2 critique report for one chapter.",
    "inputSchema": {
        "json": {
            "type": "object",
            "required": ["score", "summary"],
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "layer1_confirmed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "layer1_overridden": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "layer2_issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["severity", "dimension", "message"],
                        "properties": {
                            "severity": {
                                "type": "string",
                                "enum": ["info", "warn", "error"],
                            },
                            "dimension": {
                                "type": "string",
                                "enum": [
                                    "plot",
                                    "character",
                                    "style",
                                    "pacing",
                                    "logic",
                                ],
                            },
                            "message": {"type": "string"},
                            "evidence_excerpt": {"type": "string"},
                        },
                    },
                },
                "cross_chapter_concerns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["chapter_refs", "message"],
                        "properties": {
                            "chapter_refs": {
                                "type": "array",
                                "items": {"type": "integer", "minimum": 1},
                            },
                            "message": {"type": "string"},
                        },
                    },
                },
                "summary": {"type": "string"},
            },
        }
    },
}


class CriticAgentError(Exception):
    """Raised when Opus 4.7 returns no tool call or malformed payload."""


class CriticAgent:
    def __init__(
        self,
        *,
        model_id: str = "claude-opus-4-7",
        region: str = "us-east-1",
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._session = aioboto3.Session()

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _converse(self, prompt: str) -> dict[str, Any]:
        async with self._session.client(
            "bedrock-runtime", region_name=self._region
        ) as client:
            resp = await client.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                toolConfig={
                    "tools": [{"toolSpec": _TOOL_SCHEMA}],
                    "toolChoice": {"tool": {"name": _TOOL_NAME}},
                },
                inferenceConfig={"maxTokens": 2000, "temperature": 0.2},
            )
        return resp

    def _extract_tool_input(self, resp: dict[str, Any]) -> dict[str, Any]:
        content = resp.get("output", {}).get("message", {}).get("content", [])
        for block in content:
            if "toolUse" in block and block["toolUse"].get("name") == _TOOL_NAME:
                return block["toolUse"].get("input", {})
        raise CriticAgentError("Opus did not invoke emit_critique_report tool")

    async def run(
        self,
        *,
        template: str,
        ctx: CriticContext,
    ) -> CritiqueReport:
        prompt = render_prompt(template=template, ctx=ctx)
        resp = await self._converse(prompt)
        tool_input = self._extract_tool_input(resp)
        return self._build_report(tool_input, ctx)

    def _build_report(
        self, tool_input: dict[str, Any], ctx: CriticContext
    ) -> CritiqueReport:
        return CritiqueReport.model_validate(
            {
                "generation_id": ctx.generation_id,
                "team_id": ctx.team_id,
                "chapter_idx": ctx.chapter_idx,
                "model": self._model_id,
                "score": tool_input.get("score", 0),
                "layer1_confirmed": tool_input.get("layer1_confirmed", []),
                "layer1_overridden": tool_input.get("layer1_overridden", []),
                "layer2_issues": tool_input.get("layer2_issues", []),
                "cross_chapter_concerns": tool_input.get(
                    "cross_chapter_concerns", []
                ),
                "summary": tool_input.get("summary", ""),
                "minimal": False,
                "created_at": datetime.now(UTC),
            }
        )


def minimal_failure_report(ctx: CriticContext, reason: str) -> CritiqueReport:
    """Produce a placeholder report when CriticAgent exhausts retries (N3=A)."""
    return CritiqueReport(
        generation_id=ctx.generation_id,
        team_id=ctx.team_id,
        chapter_idx=ctx.chapter_idx,
        score=0,
        layer1_confirmed=[],
        layer1_overridden=[],
        layer2_issues=[],
        cross_chapter_concerns=[],
        summary=f"critic_failed: {reason[:180]}",
        minimal=True,
        created_at=datetime.now(UTC),
    )
