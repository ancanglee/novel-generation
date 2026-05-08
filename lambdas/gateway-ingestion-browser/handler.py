"""Gateway target: ingestion-browser.

Thin proxy: invokes AgentCore Browser (StartBrowserSession → page render → Stop).
The actual CDP page rendering is delegated to the `ingestion-browser-render`
Step Functions task (ECS Fargate with playwright) because Lambda cannot run
headless Chromium comfortably.

What this Lambda does:
1. Validates inputs.
2. Calls `StartBrowserSession` and returns the `liveViewUrl` + `sessionId` so the
   agent can stream it; the agent is expected to call `render_html` endpoint on the
   worker-ingestion ECS task which does the actual page.goto() via CDP.
3. Optionally, if `INLINE_RENDER=1` and a Fargate URL is set, calls the worker-ingestion
   sync HTTP endpoint (internal-only) to render and return HTML directly.

For V1 we always return the sessionId/streamEndpoint; the agent's client-side code
(which runs inside the agent runtime container that DOES have playwright) does the
CDP connect — keeping Lambda thin and within 15 min hard cap.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

log = logging.getLogger("gateway_ingestion_browser")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")
BROWSER_ID = os.environ.get("AGENTCORE_BROWSER_IDENTIFIER", "DEFAULT")

_bac = boto3.client("bedrock-agentcore", region_name=REGION)


def _json(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
        "isError": is_error,
        "structuredContent": data if isinstance(data, dict) else {"value": data},
    }


def _err(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"ERROR: {msg}"}], "isError": True}


def _render_with_browser(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    job_id = args["job_id"]
    timeout = max(30, min(int(args.get("timeout_seconds", 60)) + 30, 120))

    resp = _bac.start_browser_session(
        browserIdentifier=BROWSER_ID,
        sessionTimeoutSeconds=timeout,
        viewPort={"width": 1280, "height": 800},
    )
    streams = resp.get("streams") or {}
    automation = streams.get("automationStream") or {}
    return _json(
        {
            "sessionId": resp["sessionId"],
            "browserIdentifier": BROWSER_ID,
            "streamEndpoint": automation.get("uri"),
            "liveViewUrl": resp.get("liveViewUrl"),
            "target_url": url,
            "job_id": job_id,
            "instructions": (
                "Connect via Chrome DevTools Protocol to streamEndpoint, "
                "navigate to target_url, extract HTML, then call "
                "bedrock-agentcore.stop_browser_session to release the slot."
            ),
        }
    )


_HANDLERS = {"render_with_browser": _render_with_browser}


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
