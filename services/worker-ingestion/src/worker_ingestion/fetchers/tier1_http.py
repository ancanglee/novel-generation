"""Tier 1: httpx-based HTTP fetch with downgrade signals."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from worker_ingestion.robots import USER_AGENT

_JS_ONLY_MARKERS = (
    "enable javascript",
    "please enable js",
    "您的浏览器不支持",
    "请开启 JavaScript",
)


@dataclass(frozen=True)
class Tier1Result:
    status_code: int
    url: str
    html: str
    headers: dict[str, str]


class Tier1Failure(Exception):
    def __init__(self, reason: str, *, status: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


async def fetch(url: str, timeout: float = 10.0) -> Tier1Result:
    """Fetch url via httpx with identifying UA.

    Raises Tier1Failure when the caller should consider Tier 2 fallback.
    robots.txt check is expected to happen upstream.
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
    except httpx.TimeoutException as e:
        raise Tier1Failure("timeout") from e
    except httpx.HTTPError as e:
        raise Tier1Failure(f"http-error:{type(e).__name__}") from e

    if resp.status_code in (403, 429, 503):
        raise Tier1Failure("status-blocked", status=resp.status_code)
    if 500 <= resp.status_code < 600:
        raise Tier1Failure("status-5xx", status=resp.status_code)
    if resp.status_code >= 400:
        raise Tier1Failure(f"status-{resp.status_code}", status=resp.status_code)

    html = resp.text or ""
    if _is_js_only(html):
        raise Tier1Failure("js-only")
    if len(_visible_text_approx(html)) < 200:
        raise Tier1Failure("insufficient-content")

    return Tier1Result(
        status_code=resp.status_code,
        url=str(resp.url),
        html=html,
        headers=dict(resp.headers),
    )


def _is_js_only(html: str) -> bool:
    lowered = html.lower()
    if any(m in lowered for m in _JS_ONLY_MARKERS):
        return True
    body_match = re.search(r"<body[^>]*>(.*?)</body>", lowered, re.DOTALL)
    if not body_match:
        return False
    body_text = re.sub(r"<[^>]+>", "", body_match.group(1)).strip()
    script_heavy = lowered.count("<script") > 10
    return script_heavy and len(body_text) < 100


def _visible_text_approx(html: str) -> str:
    stripped = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<style[^>]*>.*?</style>", "", stripped, flags=re.DOTALL | re.IGNORECASE)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return " ".join(stripped.split())
