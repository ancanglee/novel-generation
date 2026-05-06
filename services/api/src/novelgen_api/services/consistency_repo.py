"""Read ConsistencyReport items (SK=CONSISTENCY#{gid}#{scan_to:05d})."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from novelgen_api.deps import tenancy_table


async def list_reports(
    *, team_id: UUID, generation_id: UUID, since_chapter: int = 0, limit: int = 50
) -> list[dict[str, Any]]:
    prefix = f"CONSISTENCY#{generation_id}#"
    items = await tenancy_table().query_by_sk_prefix(
        team_id=team_id, sk_prefix=prefix, limit=limit
    )
    results = []
    for item in items:
        scan_to = int(item.get("scan_to", 0))
        if scan_to < since_chapter:
            continue
        results.append(_unpack(item))
    results.sort(key=lambda x: x["scan_to"])
    return results


def _unpack(item: dict[str, Any]) -> dict[str, Any]:
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
        "scan_from": int(item.get("scan_from", 0)),
        "scan_to": int(item.get("scan_to", 0)),
        "conflict_count": int(item.get("conflict_count", 0)),
        "memory_unavailable": bool(item.get("memory_unavailable", False)),
        "minimal": bool(item.get("minimal", False)),
        "created_at": item.get("created_at"),
        "report": report,
    }
