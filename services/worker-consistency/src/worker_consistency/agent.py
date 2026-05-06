"""ConsistencyAgent — Sonnet 4.6 cross-chapter scan via Bedrock Converse + Tool Use."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import aioboto3
from novelgen_types.critique import (
    ConflictItem,
    ConflictType,
    ConsistencyReport,
    UserAction,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .context import ConsistencyContext, render_prompt

_TOOL_NAME = "emit_consistency_report"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": "Emit cross-chapter consistency report.",
    "inputSchema": {
        "json": {
            "type": "object",
            "required": ["conflicts"],
            "properties": {
                "conflicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "type",
                            "chapter_refs",
                            "summary",
                        ],
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "character_state",
                                    "plot_hole",
                                    "timeline",
                                    "location",
                                    "relation",
                                    "worldbuilding",
                                ],
                            },
                            "chapter_refs": {
                                "type": "array",
                                "items": {"type": "integer", "minimum": 1},
                                "minItems": 1,
                                "maxItems": 10,
                            },
                            "summary": {"type": "string"},
                            "evidence": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 10,
                            },
                        },
                    },
                },
            },
        }
    },
}


class ConsistencyAgentError(Exception):
    pass


class ConsistencyAgent:
    def __init__(
        self,
        *,
        model_id: str = "claude-sonnet-4-6",
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
                inferenceConfig={"maxTokens": 4000, "temperature": 0.1},
            )
        return resp

    def _extract_conflicts(self, resp: dict[str, Any]) -> list[dict[str, Any]]:
        content = resp.get("output", {}).get("message", {}).get("content", [])
        for block in content:
            if "toolUse" in block and block["toolUse"].get("name") == _TOOL_NAME:
                return block["toolUse"].get("input", {}).get("conflicts", [])
        raise ConsistencyAgentError(
            "Sonnet did not invoke emit_consistency_report tool"
        )

    async def run(
        self,
        *,
        template: str,
        ctx: ConsistencyContext,
    ) -> tuple[ConsistencyReport, list[ConflictItem]]:
        prompt = render_prompt(template=template, ctx=ctx)
        resp = await self._converse(prompt)
        raw_conflicts = self._extract_conflicts(resp)
        return self._assemble(raw_conflicts, ctx)

    def _assemble(
        self,
        raw_conflicts: list[dict[str, Any]],
        ctx: ConsistencyContext,
    ) -> tuple[ConsistencyReport, list[ConflictItem]]:
        now = datetime.now(UTC)
        conflicts: list[ConflictItem] = []
        for raw in raw_conflicts:
            ci = ConflictItem(
                conflict_id=uuid4(),
                generation_id=ctx.generation_id,
                team_id=ctx.team_id,
                scan_to=ctx.scan_to,
                type=ConflictType(raw["type"]),
                chapter_refs=list(raw["chapter_refs"]),
                summary=raw["summary"],
                evidence=list(raw.get("evidence", [])),
                rewrite_attempts=0,
                frozen=False,
                user_action=UserAction.OPEN,
                created_at=now,
                updated_at=now,
            )
            conflicts.append(ci)

        report = ConsistencyReport(
            generation_id=ctx.generation_id,
            team_id=ctx.team_id,
            scan_from=ctx.scan_from,
            scan_to=ctx.scan_to,
            model=self._model_id,
            conflict_ids=[c.conflict_id for c in conflicts],
            memory_unavailable=ctx.memory_unavailable,
            characters_scanned=[
                UUID(s["character_id"])
                for s in ctx.character_snapshots
                if s.get("character_id")
            ],
            minimal=False,
            created_at=now,
        )
        return report, conflicts


def minimal_failure_report(ctx: ConsistencyContext) -> ConsistencyReport:
    return ConsistencyReport(
        generation_id=ctx.generation_id,
        team_id=ctx.team_id,
        scan_from=ctx.scan_from,
        scan_to=ctx.scan_to,
        conflict_ids=[],
        memory_unavailable=ctx.memory_unavailable,
        minimal=True,
        created_at=datetime.now(UTC),
    )
