"""Supervisor checkpoint: DDB write every N steps for Spot recovery (NFR-2.1, N5=A)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from novelgen_obs import get_logger
from novelgen_storage import DynamoDBAdapter, build_team_pk

log = get_logger("worker-analysis.checkpoint")

CHECKPOINT_INTERVAL = 5
CHECKPOINT_TTL_SECONDS = 24 * 3600


class CheckpointStore:
    def __init__(self, jobs_table: DynamoDBAdapter) -> None:
        self._ddb = jobs_table

    async def save(
        self,
        team_id: UUID,
        job_id: UUID,
        step_history: list[str],
        partial_results: dict[str, Any],
        current_goal: str,
    ) -> None:
        ttl = int(datetime.now(tz=timezone.utc).timestamp()) + CHECKPOINT_TTL_SECONDS
        await self._ddb.put(
            team_id=team_id,
            item={
                "pk": build_team_pk(team_id),
                "sk": f"CHECKPOINT#{job_id}",
                "job_id": str(job_id),
                "step_history": step_history,
                "partial_results": json.dumps(partial_results, default=str),
                "current_goal": current_goal,
                "saved_at": datetime.now(tz=timezone.utc).isoformat(),
                "ttl": ttl,
            },
        )
        log.info("checkpoint saved", extra={"job_id": str(job_id), "steps": len(step_history)})

    async def load(self, team_id: UUID, job_id: UUID) -> dict[str, Any] | None:
        item = await self._ddb.get(
            team_id=team_id,
            pk=build_team_pk(team_id),
            sk=f"CHECKPOINT#{job_id}",
        )
        if not item:
            return None
        try:
            partial = json.loads(item.get("partial_results", "{}"))
        except json.JSONDecodeError:
            partial = {}
        return {
            "step_history": item.get("step_history", []),
            "partial_results": partial,
            "current_goal": item.get("current_goal", ""),
        }

    async def clear(self, team_id: UUID, job_id: UUID) -> None:
        await self._ddb.delete(
            team_id=team_id, pk=build_team_pk(team_id), sk=f"CHECKPOINT#{job_id}"
        )
