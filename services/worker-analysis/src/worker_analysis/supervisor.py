"""Supervisor agent: Opus 4.7 driven orchestration of 9 sub-agent tools.

Implements R1 (Supervisor with 50-step / 15min hard limits) and F1=B Supervisor mode.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Awaitable, Callable
from uuid import UUID

from novelgen_obs import emit_metric, get_logger

from worker_analysis.agents._bedrock import invoke_tool
from worker_analysis.checkpoint import CHECKPOINT_INTERVAL, CheckpointStore
from worker_analysis.prompts import load_prompt

log = get_logger("worker-analysis.supervisor")

MAX_STEPS = 50
MAX_SECONDS = 15 * 60
SUPERVISOR_MODEL = "anthropic.claude-opus-4-7-v1:0"


@dataclass
class SupervisorContext:
    team_id: UUID
    job_id: UUID
    novel_id: UUID
    chapter_count: int
    step_history: list[str] = field(default_factory=list)
    partial_results: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    current_goal: str = "analyze the novel end-to-end"

    @property
    def step_count(self) -> int:
        return len(self.step_history)


_NEXT_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tool": {
            "type": "string",
            "enum": [
                "sample_chapters",
                "classify_tags",
                "extract_characters_global",
                "extract_map_global",
                "analyze_style",
                "extract_chapter_all",
                "rewrite_character_profile",
                "write_memory",
                "finalize_report",
            ],
        },
        "args": {"type": "object"},
        "reason": {"type": "string", "maxLength": 400},
    },
    "required": ["tool", "args", "reason"],
}


ToolDispatcher = Callable[[str, dict[str, Any], SupervisorContext], Awaitable[dict[str, Any]]]


class Supervisor:
    def __init__(
        self,
        dispatcher: ToolDispatcher,
        checkpoint: CheckpointStore,
        *,
        model_id: str = SUPERVISOR_MODEL,
        region: str = "us-east-1",
    ) -> None:
        self._dispatcher = dispatcher
        self._checkpoint = checkpoint
        self._model_id = model_id
        self._region = region
        self._system_prompt = load_prompt("supervisor")

    async def run(self, ctx: SupervisorContext) -> dict[str, Any]:
        start = time.monotonic()
        last_call: tuple[str, str] | None = None
        last_call_count = 0

        while True:
            if ctx.step_count >= MAX_STEPS:
                ctx.warnings.append(f"forced finalize: reached {MAX_STEPS} steps")
                return await self._force_finalize(ctx)
            if time.monotonic() - start > MAX_SECONDS:
                ctx.warnings.append("forced finalize: exceeded 15 min budget")
                return await self._force_finalize(ctx)

            step = await self._decide_next(ctx)
            tool = step.get("tool", "finalize_report")
            args = step.get("args", {}) or {}
            reason = step.get("reason", "")

            sig = (tool, _signature(args))
            if last_call is not None and last_call == sig:
                last_call_count += 1
                if last_call_count >= 2:
                    ctx.warnings.append(f"skipping repeated call: {tool}")
                    continue
            else:
                last_call = sig
                last_call_count = 1

            ctx.step_history.append(tool)
            emit_metric(
                "SupervisorStepCount",
                float(ctx.step_count),
                dimensions={"JobId": str(ctx.job_id)},
            )
            log.info(
                "supervisor step",
                extra={"step": ctx.step_count, "tool": tool, "reason": reason[:120]},
            )

            if tool == "finalize_report":
                return args or ctx.partial_results

            try:
                result = await self._dispatcher(tool, args, ctx)
                ctx.partial_results[f"{tool}:{ctx.step_count}"] = result
            except Exception as e:
                log.exception("sub-agent failed")
                ctx.warnings.append(f"{tool} failed: {e}")

            if ctx.step_count % CHECKPOINT_INTERVAL == 0:
                await self._checkpoint.save(
                    team_id=ctx.team_id,
                    job_id=ctx.job_id,
                    step_history=ctx.step_history,
                    partial_results=ctx.partial_results,
                    current_goal=ctx.current_goal,
                )

    async def _decide_next(self, ctx: SupervisorContext) -> dict[str, Any]:
        summary = _summarize_context(ctx)
        result = await invoke_tool(
            model_id=self._model_id,
            system_prompt=self._system_prompt,
            user_text=summary,
            tool_name="next_step",
            tool_schema=_NEXT_STEP_SCHEMA,
            region=self._region,
            stage="supervisor",
            max_tokens=1200,
        )
        if not result.input:
            return {"tool": "finalize_report", "args": {}, "reason": "empty supervisor response"}
        return result.input

    async def _force_finalize(self, ctx: SupervisorContext) -> dict[str, Any]:
        log.warning(
            "force finalize",
            extra={"job_id": str(ctx.job_id), "steps": ctx.step_count, "warnings": ctx.warnings},
        )
        return {"partial_results": ctx.partial_results, "warnings": ctx.warnings, "forced": True}


def _signature(args: dict[str, Any]) -> str:
    try:
        items = sorted((k, str(v)[:80]) for k, v in args.items())
        return ";".join(f"{k}={v}" for k, v in items)
    except Exception:
        return ""


def _summarize_context(ctx: SupervisorContext) -> str:
    recent = ctx.step_history[-10:]
    summary_lines = [
        f"Novel ID: {ctx.novel_id}",
        f"Team ID: {ctx.team_id}",
        f"Chapter count: {ctx.chapter_count}",
        f"Goal: {ctx.current_goal}",
        f"Step count: {ctx.step_count}/{MAX_STEPS}",
        f"Recent steps: {recent}",
        f"Partial keys: {list(ctx.partial_results.keys())[:20]}",
        f"Warnings: {ctx.warnings[-5:]}",
    ]
    budget_left = timedelta(seconds=MAX_SECONDS)
    summary_lines.append(f"Time budget: {budget_left}")
    return "\n".join(summary_lines)
