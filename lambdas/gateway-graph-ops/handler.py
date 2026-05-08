"""Gateway target: graph-ops (Neptune).

Thin Lambda in VPC (with Neptune access). Translates MCP tool calls into openCypher
HTTPS requests to the Neptune cluster endpoint.

Env:
- NEPTUNE_ENDPOINT (https://<cluster>.<region>.neptune.amazonaws.com:8182)
- AWS_REGION
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
import httpx
from requests_aws4auth import AWS4Auth

log = logging.getLogger("gateway_graph_ops")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")
ENDPOINT = os.environ["NEPTUNE_ENDPOINT"].rstrip("/")


def _sigv4_auth() -> AWS4Auth:
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    return AWS4Auth(
        creds.access_key, creds.secret_key, REGION, "neptune-db", session_token=creds.token
    )


def _json(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _err(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


def _opencypher(query: str, params: dict[str, Any]) -> dict[str, Any]:
    # Neptune /openCypher endpoint accepts form-encoded "query" + "parameters" (JSON).
    auth = _sigv4_auth()
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(
            f"{ENDPOINT}/openCypher",
            data={"query": query, "parameters": json.dumps(params)},
            auth=(auth, None),  # type: ignore[arg-type]
        )
    resp.raise_for_status()
    return resp.json()


def _upsert_node(args: dict[str, Any]) -> dict[str, Any]:
    q = (
        "MERGE (n:`{label}` {{team_id:$team_id, novel_id:$novel_id, node_id:$node_id}}) "
        "SET n += $props "
        "RETURN n.node_id"
    ).format(label=args["label"])
    params = {
        "team_id": args["team_id"],
        "novel_id": args["novel_id"],
        "node_id": args["node_id"],
        "props": args.get("properties") or {},
    }
    res = _opencypher(q, params)
    return _json({"result": res.get("results", [])})


def _upsert_edge(args: dict[str, Any]) -> dict[str, Any]:
    q = (
        "MATCH (a:`{fl}` {{team_id:$team_id, novel_id:$novel_id, node_id:$from_id}}) "
        "MATCH (b:`{tl}` {{team_id:$team_id, novel_id:$novel_id, node_id:$to_id}}) "
        "MERGE (a)-[r:`{et}`]->(b) "
        "SET r += $props "
        "RETURN type(r)"
    ).format(fl=args["from_label"], tl=args["to_label"], et=args["edge_type"])
    params = {
        "team_id": args["team_id"],
        "novel_id": args["novel_id"],
        "from_id": args["from_id"],
        "to_id": args["to_id"],
        "props": args.get("properties") or {},
    }
    res = _opencypher(q, params)
    return _json({"result": res.get("results", [])})


def _neighbors(args: dict[str, Any]) -> dict[str, Any]:
    edge_filter = f":`{args['edge_type']}`" if args.get("edge_type") else ""
    q = (
        "MATCH (n {{team_id:$team_id, novel_id:$novel_id, node_id:$node_id}})"
        "-[r{et}]->(m) "
        "RETURN labels(m) AS labels, properties(m) AS properties LIMIT $limit"
    ).format(et=edge_filter)
    params = {
        "team_id": args["team_id"],
        "novel_id": args["novel_id"],
        "node_id": args["node_id"],
        "limit": int(args.get("limit", 50)),
    }
    res = _opencypher(q, params)
    return _json({"neighbors": res.get("results", [])})


_HANDLERS = {"upsert_node": _upsert_node, "upsert_edge": _upsert_edge, "neighbors": _neighbors}


def handler(event: dict[str, Any], _ctx: Any) -> dict[str, Any]:
    tool = event.get("toolName") or event.get("name")
    args = event.get("arguments") or {}
    if tool not in _HANDLERS:
        return _err(f"unknown tool: {tool!r}")
    try:
        return _HANDLERS[tool](args)
    except KeyError as e:
        return _err(f"missing argument: {e}")
    except Exception as e:  # noqa: BLE001
        log.exception("handler_failed tool=%s", tool)
        return _err(f"{type(e).__name__}: {e}")
