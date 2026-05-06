"""Lambda: load-generation-context for ChapterStateMachine.

Invoked as the first step of ChapterStateMachine. Reads the Generation row,
calls MemoryFacade.hybrid_search once to fetch 3 style reference excerpts,
and writes a GEN_CONTEXT row with 24h TTL for worker-generation to consume.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3

TENANCY_TABLE = os.environ["TENANCY_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]

_ddb = boto3.resource("dynamodb")
_tenancy = _ddb.Table(TENANCY_TABLE)
_jobs = _ddb.Table(JOBS_TABLE)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    team_id = event["team_id"]
    generation_id = event["generation_id"]

    gen = _tenancy.get_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"GEN#{generation_id}"}
    ).get("Item") or {}

    # In production, this would call MemoryFacade.hybrid_search(top_k=3) via
    # shared Lambda layer or by invoking a helper service. V1 leaves the list
    # empty and the ChapterAgent will render a fallback block.
    style_reference_excerpts: list[str] = []

    ttl = int((datetime.now(tz=timezone.utc) + timedelta(hours=24)).timestamp())
    chapter_count = int(gen.get("target_chapter_count", 0))

    _jobs.put_item(
        Item={
            "pk": f"TEAM#{team_id}",
            "sk": f"GEN_CONTEXT#{generation_id}",
            "generation_id": generation_id,
            "team_id": team_id,
            "style_vector": gen.get("style_vector", {}),
            "style_reference_excerpts": style_reference_excerpts,
            "outline_items": gen.get("outline_items", []),
            "recent_facts": [],
            "ttl": ttl,
        }
    )

    return {
        "context": {
            "generation_id": generation_id,
            "team_id": team_id,
            "chapter_count": chapter_count,
        }
    }
