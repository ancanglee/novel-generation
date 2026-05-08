"""Gateway target: vector-ops (OpenSearch Serverless).

Index per novel: `novelgen-{team}-{novel}-facts` (created on first write).

Tools:
- index_vector(team_id, novel_id, chunk_id, embedding, payload)
- search_similar(team_id, novel_id, embedding, top_k?, filters?)
- hybrid_search(team_id, novel_id, query_text, query_embed, top_k?)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

log = logging.getLogger("gateway_vector_ops")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")
AOSS_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"].replace("https://", "").replace("http://", "")


def _client() -> OpenSearch:
    creds = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(creds, REGION, "aoss")
    return OpenSearch(
        hosts=[{"host": AOSS_ENDPOINT, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=20,
    )


def _index(team_id: str, novel_id: str) -> str:
    return f"novelgen-{team_id}-{novel_id}-facts".lower()


def _json(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _err(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


def _index_vector(args: dict[str, Any]) -> dict[str, Any]:
    os_client = _client()
    idx = _index(args["team_id"], args["novel_id"])
    body = {"embedding": args["embedding"], **(args.get("payload") or {})}
    resp = os_client.index(index=idx, id=args["chunk_id"], body=body, refresh=False)
    return _json({"result": resp.get("result")})


def _search_similar(args: dict[str, Any]) -> dict[str, Any]:
    os_client = _client()
    idx = _index(args["team_id"], args["novel_id"])
    top_k = int(args.get("top_k", 10))
    q = {
        "size": top_k,
        "query": {"knn": {"embedding": {"vector": args["embedding"], "k": top_k}}},
    }
    if args.get("filters"):
        q["post_filter"] = {"bool": {"must": [{"term": {k: v}} for k, v in args["filters"].items()]}}
    resp = os_client.search(index=idx, body=q)
    return _json({"hits": resp.get("hits", {}).get("hits", [])})


def _hybrid_search(args: dict[str, Any]) -> dict[str, Any]:
    os_client = _client()
    idx = _index(args["team_id"], args["novel_id"])
    top_k = int(args.get("top_k", 10))
    q = {
        "size": top_k,
        "query": {
            "hybrid": {
                "queries": [
                    {"match": {"content_text": args["query_text"]}},
                    {"knn": {"embedding": {"vector": args["query_embed"], "k": top_k}}},
                ]
            }
        },
    }
    resp = os_client.search(index=idx, body=q)
    return _json({"hits": resp.get("hits", {}).get("hits", [])})


_HANDLERS = {
    "index_vector": _index_vector,
    "search_similar": _search_similar,
    "hybrid_search": _hybrid_search,
}


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
