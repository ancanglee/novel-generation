"""Gateway target: ddb-jobs.

Tools:
- put_checkpoint(team_id, job_id, step, state)
- get_checkpoint(team_id, job_id, step)
- advance_scan_cursor(team_id, novel_id, chapter_idx)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

log = logging.getLogger("gateway_ddb_jobs")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")
JOBS_TABLE = os.environ["JOBS_TABLE"]

_ddb = boto3.resource("dynamodb", region_name=REGION)
_jobs = _ddb.Table(JOBS_TABLE)


def _json(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _err(msg: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"ERROR: {msg}"}],
        "isError": True,
    }


def _put_checkpoint(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    job_id = args["job_id"]
    step = args["step"]
    state = args["state"]
    _jobs.put_item(
        Item={
            "pk": f"TEAM#{team_id}",
            "sk": f"CHECKPOINT#{job_id}#{step}",
            "state": state,
        }
    )
    return _json({"ok": True})


def _get_checkpoint(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    job_id = args["job_id"]
    step = args["step"]
    resp = _jobs.get_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"CHECKPOINT#{job_id}#{step}"},
        ConsistentRead=True,
    )
    return _json({"state": (resp.get("Item") or {}).get("state")})


def _advance_scan(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args["team_id"]
    novel_id = args["novel_id"]
    chapter_idx = int(args["chapter_idx"])
    _jobs.update_item(
        Key={"pk": f"TEAM#{team_id}", "sk": f"SCAN#{novel_id}"},
        UpdateExpression="SET last_scanned = :c",
        ConditionExpression="attribute_not_exists(last_scanned) OR last_scanned < :c",
        ExpressionAttributeValues={":c": chapter_idx},
    )
    return _json({"advanced_to": chapter_idx})


_HANDLERS = {
    "put_checkpoint": _put_checkpoint,
    "get_checkpoint": _get_checkpoint,
    "advance_scan_cursor": _advance_scan,
}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    tool = event.get("toolName") or event.get("name")
    args = event.get("arguments") or {}
    if tool not in _HANDLERS:
        return _err(f"unknown tool: {tool!r}")
    try:
        return _HANDLERS[tool](args)
    except KeyError as e:
        return _err(f"missing argument: {e}")
    except _jobs.meta.client.exceptions.ConditionalCheckFailedException:
        return _json({"advanced_to": None, "skipped": True})
    except Exception as e:  # noqa: BLE001
        log.exception("handler_failed tool=%s", tool)
        return _err(f"{type(e).__name__}: {e}")
