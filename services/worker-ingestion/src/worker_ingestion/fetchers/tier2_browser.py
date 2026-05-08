"""Tier 2: AgentCore Browser fetch (JS-rendered) with global concurrency slot.

Flow:
1. Acquire a slot from the global BrowserPool (DDB CAS) — throttles us client-side.
2. StartBrowserSession on AgentCore Browser (data plane). Returns a CDP wss endpoint.
3. playwright.connect_over_cdp to the endpoint, goto(url, wait_until=networkidle),
   extract `content()`.
4. StopBrowserSession (finally) to return capacity to AgentCore.

Timeouts:
- AgentCore Browser session: 120s hard cap (we request 120).
- We set asyncio.wait_for(100s) so our own StopBrowserSession runs before AgentCore's
  force-reap at 120s, preventing zombie sessions.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import aioboto3
from novelgen_browser_pool import BrowserPool


@dataclass(frozen=True)
class Tier2Result:
    url: str
    html: str


class Tier2Failure(Exception):
    pass


async def _render_with_agentcore(url: str, *, timeout_seconds: int = 60) -> str:
    """Open an AgentCore Browser session, render URL via CDP, return HTML.

    Raises Tier2Failure on any underlying error (network, CDP, timeout).
    """
    region = os.environ.get("AWS_REGION", "us-west-2")
    browser_identifier = os.environ.get("AGENTCORE_BROWSER_IDENTIFIER", "DEFAULT")
    session_timeout = max(min(timeout_seconds + 30, 120), 30)

    session = aioboto3.Session()
    async with session.client("bedrock-agentcore", region_name=region) as data:
        try:
            resp = await data.start_browser_session(
                browserIdentifier=browser_identifier,
                sessionTimeoutSeconds=session_timeout,
                viewPort={"width": 1280, "height": 800},
            )
        except Exception as e:
            raise Tier2Failure(f"StartBrowserSession failed: {e}") from e

        session_id = resp["sessionId"]
        stream_endpoint = _extract_cdp_endpoint(resp)
        try:
            html = await asyncio.wait_for(
                _render_via_cdp(stream_endpoint, url),
                timeout=min(timeout_seconds, session_timeout - 20),
            )
        except TimeoutError as e:
            raise Tier2Failure(f"render timeout after {timeout_seconds}s") from e
        except Exception as e:
            raise Tier2Failure(f"cdp render failed: {e}") from e
        finally:
            try:
                await data.stop_browser_session(
                    browserIdentifier=browser_identifier, sessionId=session_id
                )
            except Exception:
                # Best effort — AgentCore will force-reap on TTL.
                pass
        return html


def _extract_cdp_endpoint(resp: dict[str, Any]) -> str:
    """Pull the wss CDP endpoint from StartBrowserSession response.

    AgentCore returns a streams block; we target the automation stream URI.
    """
    streams = resp.get("streams") or {}
    automation = streams.get("automationStream") or {}
    uri = automation.get("uri") or resp.get("streamEndpoint")
    if not uri:
        raise Tier2Failure(
            "StartBrowserSession returned no automation stream URI; response keys: "
            + ",".join(resp.keys())
        )
    return uri


async def _render_via_cdp(cdp_endpoint: str, url: str) -> str:
    """Connect to CDP over wss, load URL, return full rendered HTML."""
    # Lazy import: playwright is optional for dev machines without browsers.
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp_endpoint)
        try:
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            return await page.content()
        finally:
            await browser.close()


async def fetch(
    url: str, job_id: str, pool: BrowserPool, timeout_seconds: int = 60
) -> Tier2Result:
    """Acquire pool slot → AgentCore Browser render → return HTML."""
    async with pool.slot(job_id):
        html = await _render_with_agentcore(url, timeout_seconds=timeout_seconds)
    if len(html.strip()) < 200:
        raise Tier2Failure("tier2-insufficient-content")
    return Tier2Result(url=url, html=html)
