"""Gateway target: memory-facade.

Exposes 3 MCP tools:
- remember(team_id, novel_id, facts[]) — writes Facts to AgentCore Memory.
- recall(team_id, novel_id, query, top_k?) — semantic retrieval from Memory.
- get_character(team_id, novel_id, character_id, at_chapter?) — latest snapshot.

Deployed as a single Lambda, routed by `event.toolName`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3

log = logging.getLogger("gateway_memory_facade")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")
MEMORY_ID = os.environ["AGENTCORE_MEMORY_ID"]

_client = boto3.client("bedrock-agentcore", region_name=REGION)


def _text_result(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _json_result(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _error(msg: str) -> dict[str, Any]:
    return _text_result(f"ERROR: {msg}", is_error=True)


def _actor(team_id: str, novel_id: str) -> str:
    return f"{team_id}:{novel_id}"


def _namespace(team_id: str, novel_id: str) -> str:
    return f"{team_id}/{novel_id}"


def _do_remember(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    novel_id = args["novel_id"]
    facts: list[dict[str, Any]] = args.get("facts") or []
    if not facts:
        return _json_result({"written": 0})

    payload = [
        {
            "conversational": {
                "role": "USER",
                "content": {"text": json.dumps(f, ensure_ascii=False)},
            }
        }
        for f in facts
    ]

    _client.create_event(
        memoryId=MEMORY_ID,
        actorId=_actor(team_id, novel_id),
        sessionId=args.get("session_id") or "facts",
        eventTimestamp=datetime.now(tz=UTC),
        payload=payload,
    )
    return _json_result({"written": len(facts)})


def _do_recall(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    novel_id = args["novel_id"]
    query = args["query"]
    top_k = int(args.get("top_k", 20))
    resp = _client.retrieve_memory_records(
        memoryId=MEMORY_ID,
        namespace=_namespace(team_id, novel_id),
        searchCriteria={"searchQuery": query, "topK": top_k},
    )
    hits = resp.get("memoryRecordSummaries") or resp.get("memoryRecords") or []
    return _json_result({"hits": hits})


def _do_get_character(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    novel_id = args["novel_id"]
    character_id = args["character_id"]
    at_chapter = args.get("at_chapter")

    q = f"character snapshot for {character_id}"
    if at_chapter is not None:
        q += f" at or before chapter {at_chapter}"

    resp = _client.retrieve_memory_records(
        memoryId=MEMORY_ID,
        namespace=_namespace(team_id, novel_id),
        searchCriteria={"searchQuery": q, "topK": 10},
    )
    hits = resp.get("memoryRecordSummaries") or resp.get("memoryRecords") or []
    for rec in hits:
        content = rec.get("content") or {}
        text = content.get("text") if isinstance(content, dict) else None
        if not text:
            continue
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            continue
        inner = payload.get("content") or {}
        if inner.get("character_id") == character_id:
            if at_chapter is not None and int(inner.get("chapter", 0)) > int(at_chapter):
                continue
            return _json_result({"snapshot": inner})
    return _json_result({"snapshot": None})


_HANDLERS = {
    "remember": _do_remember,
    "recall": _do_recall,
    "get_character": _do_get_character,
}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    tool = event.get("toolName") or event.get("name")
    args = event.get("arguments") or {}
    if tool not in _HANDLERS:
        return _error(f"unknown tool: {tool!r}")
    try:
        return _HANDLERS[tool](args)
    except KeyError as e:
        return _error(f"missing argument: {e}")
    except Exception as e:  # noqa: BLE001
        log.exception("handler_failed tool=%s", tool)
        return _error(f"{type(e).__name__}: {e}")
