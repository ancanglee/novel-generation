"""Gateway target: ingestion-fetch.

Tier-1 HTTP fetch (no JS rendering). Tier-2 (AgentCore Browser) lives in
gateway-ingestion-browser. Tier-3 (human-in-the-loop) is a ticket, not a tool.

Tools:
- fetch_public_domain(source_id, query, limit?) — search public corpora.
- fetch_url(url) — plain HTTP GET with polite UA.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger("gateway_ingestion_fetch")
log.setLevel(logging.INFO)

_UA = "NovelGenBot/0.1 (+https://novelgen.example.com/bot)"


def _json(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _err(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


_SOURCES = {
    "gutenberg": "https://gutendex.com/books/?search={q}",
    "ctext": "https://ctext.org/searchresults?searchu={q}",
    "wikisource": "https://zh.wikisource.org/w/index.php?search={q}",
}


def _fetch_public_domain(args: dict[str, Any]) -> dict[str, Any]:
    source = args["source_id"]
    if source not in _SOURCES:
        return _err(f"unknown source: {source}")
    url = _SOURCES[source].format(q=quote(args["query"]))
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": _UA})
    return _json({"url": str(resp.url), "status": resp.status_code, "text": resp.text[:200000]})


def _fetch_url(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": _UA, "Accept-Language": "zh,en"})
    return _json(
        {
            "url": str(resp.url),
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "text": resp.text[:400000],
        }
    )


_HANDLERS = {
    "fetch_public_domain": _fetch_public_domain,
    "fetch_url": _fetch_url,
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
    except httpx.HTTPError as e:
        return _err(f"http error: {e}")
    except Exception as e:  # noqa: BLE001
        log.exception("handler_failed tool=%s", tool)
        return _err(f"{type(e).__name__}: {e}")
