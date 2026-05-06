"""Lambda: load novel metadata for AnalysisStateMachine.

Returns chapter count, word count, and optionally a list of chapter titles so the
Supervisor's first sample_chapters call has enough context.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

TENANCY_TABLE = os.environ["TENANCY_TABLE"]
_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TENANCY_TABLE)

MAX_TITLES = 500  # prompt size guard


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    team_id = event["team_id"]
    novel_id = event["novel_id"]

    novel = _table.get_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"NOVEL#{novel_id}"}
    ).get("Item") or {}

    chapters = []
    last_key = None
    while True:
        kwargs = {
            "KeyConditionExpression": Key("pk").eq(f"TEAM#{team_id}")
            & Key("sk").begins_with(f"CHAPTER#{novel_id}#"),
            "ProjectionExpression": "chapter_idx, title, word_count",
            "Limit": 250,
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = _table.query(**kwargs)
        chapters.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break

    chapters.sort(key=lambda c: int(c.get("chapter_idx", 0)))
    titles = [c.get("title", "") for c in chapters[:MAX_TITLES]]

    return {
        "novel_id": novel_id,
        "team_id": team_id,
        "chapter_count": len(chapters),
        "word_count": int(novel.get("word_count", 0)),
        "title": novel.get("title", ""),
        "chapter_titles": titles,
    }
