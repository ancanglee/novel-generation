"""Read CritiqueReport items (SK=CRITIQUE#{gid}#{idx:05d})."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from novelgen_storage import build_team_pk

from novelgen_api.deps import tenancy_table


async def get_critique(
    *, team_id: UUID, generation_id: UUID, chapter_idx: int
) -> dict[str, Any] | None:
    item = await tenancy_table().get(
        team_id=team_id,
        pk=build_team_pk(team_id),
        sk=f"CRITIQUE#{generation_id}#{chapter_idx:05d}",
    )
    if not item:
        return None
    return _unpack(item)


def _unpack(item: dict[str, Any]) -> dict[str, Any]:
    """Inflate the nested `report` JSON blob into a dict."""
    raw = item.get("report")
    if isinstance(raw, str):
        try:
            report = json.loads(raw)
        except Exception:
            report = {}
    elif isinstance(raw, dict):
        report = raw
    else:
        report = {}
    return {
        "chapter_idx": int(item.get("chapter_idx", 0)),
        "score": int(item.get("score", 0)),
        "minimal": bool(item.get("minimal", False)),
        "created_at": item.get("created_at"),
        "report": report,
    }
