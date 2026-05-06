"""ConflictItem repository: rewrite_attempts / frozen transitions.

Locator SK = CONFLICT#{generation_id}#{conflict_id}.
DDB conditional update handles concurrency: two racing requests cannot both
pass the `frozen = false` precondition when attempts reach `max_attempts`.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC
from typing import Any
from uuid import UUID

from novelgen_storage import build_team_pk

from novelgen_api.deps import tenancy_table

_METRIC_NS = "novelgen/critic"


class ConflictNotFound(Exception):
    pass


class ConflictFrozen(Exception):
    """Raised when user attempts action on a frozen conflict (409)."""


@dataclass
class ConflictLocator:
    team_id: UUID
    generation_id: UUID
    conflict_id: UUID

    @property
    def pk(self) -> str:
        return build_team_pk(self.team_id)

    @property
    def sk(self) -> str:
        return f"CONFLICT#{self.generation_id}#{self.conflict_id}"


async def find(
    *, team_id: UUID, generation_id: UUID, conflict_id: UUID
) -> dict[str, Any]:
    loc = ConflictLocator(
        team_id=team_id, generation_id=generation_id, conflict_id=conflict_id
    )
    item = await tenancy_table().get(team_id=team_id, pk=loc.pk, sk=loc.sk)
    if not item:
        raise ConflictNotFound(str(conflict_id))
    return item


async def find_by_id(*, team_id: UUID, conflict_id: UUID) -> dict[str, Any]:
    """Locate by conflict_id without generation_id — scans via GSI-style prefix.

    Since CONFLICT SKs embed generation_id, we iterate known generations.
    To keep the API ergonomic, we search across all CONFLICT# items and match
    on embedded conflict_id. Limited to 200 hits — tune if needed.
    """
    build_team_pk(team_id)
    items = await tenancy_table().query_by_sk_prefix(
        team_id=team_id, sk_prefix="CONFLICT#", limit=500
    )
    needle = str(conflict_id)
    for item in items:
        sk = item.get("sk", "")
        if sk.endswith(f"#{needle}"):
            return item
    raise ConflictNotFound(str(conflict_id))


async def ignore(*, team_id: UUID, generation_id: UUID, conflict_id: UUID) -> dict[str, Any]:
    loc = ConflictLocator(
        team_id=team_id, generation_id=generation_id, conflict_id=conflict_id
    )
    attrs = await tenancy_table().update(
        team_id=team_id,
        pk=loc.pk,
        sk=loc.sk,
        update_expression="SET user_action = :a, updated_at = :t",
        expression_values={":a": "ignored", ":t": _now_iso()},
    )
    return attrs


async def request_rewrite(
    *,
    team_id: UUID,
    generation_id: UUID,
    conflict_id: UUID,
    max_attempts: int,
    env: str,
) -> dict[str, Any]:
    """Increment rewrite_attempts, freeze when reaching max.

    - frozen=true → raise ConflictFrozen (caller returns 409).
    - attempts+1 == max → set frozen=true, emit ConflictLoopDetected metric.
    - Otherwise → increment and return updated attrs.
    """
    loc = ConflictLocator(
        team_id=team_id, generation_id=generation_id, conflict_id=conflict_id
    )
    existing = await tenancy_table().get(team_id=team_id, pk=loc.pk, sk=loc.sk)
    if not existing:
        raise ConflictNotFound(str(conflict_id))
    if bool(existing.get("frozen", False)):
        raise ConflictFrozen(str(conflict_id))

    current_attempts = int(existing.get("rewrite_attempts", 0))
    new_attempts = current_attempts + 1
    will_freeze = new_attempts >= max_attempts

    try:
        attrs = await tenancy_table().update(
            team_id=team_id,
            pk=loc.pk,
            sk=loc.sk,
            update_expression=(
                "SET rewrite_attempts = :new, frozen = :f, user_action = :a, updated_at = :t"
            ),
            expression_values={
                ":new": new_attempts,
                ":f": will_freeze,
                ":cur": current_attempts,
                ":fcur": False,
                ":a": "rewrite_requested",
                ":t": _now_iso(),
            },
            condition="rewrite_attempts = :cur AND frozen = :fcur",
        )
    except Exception as exc:
        # Race: another request incremented first; translate to frozen for safety.
        raise ConflictFrozen(str(conflict_id)) from exc

    if will_freeze:
        _emit_conflict_loop_metric(env=env)

    return attrs


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _emit_conflict_loop_metric(env: str) -> None:
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": _METRIC_NS,
                    "Dimensions": [["Env"]],
                    "Metrics": [{"Name": "ConflictLoopDetected", "Unit": "Count"}],
                }
            ],
        },
        "Env": env,
        "ConflictLoopDetected": 1.0,
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
