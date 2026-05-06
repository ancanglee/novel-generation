"""Tier 2: AgentCore Browser fetch (JS-rendered) with global concurrency slot.

AgentCore Browser Python SDK bindings are not yet finalized; this module exposes the
integration surface. Real SDK wiring is deferred to U3 where Agents consume Browser
extensively. For now the client call raises NotImplementedError, so tests can patch it.
"""

from __future__ import annotations

from dataclasses import dataclass

from novelgen_browser_pool import BrowserPool


@dataclass(frozen=True)
class Tier2Result:
    url: str
    html: str


class Tier2Failure(Exception):
    pass


async def _render_with_agentcore(url: str, timeout_seconds: int = 60) -> str:
    """Invoke AgentCore Browser to load the URL and return rendered HTML.

    Placeholder: actual SDK wiring lives in U3. Tests monkey-patch this function.
    """
    raise NotImplementedError(
        "AgentCore Browser SDK call is wired in U3; monkey-patch in tests"
    )


async def fetch(url: str, job_id: str, pool: BrowserPool, timeout_seconds: int = 60) -> Tier2Result:
    """Acquire a global Browser slot, render the URL, and return HTML."""
    async with pool.slot(job_id):
        try:
            html = await _render_with_agentcore(url, timeout_seconds=timeout_seconds)
        except Exception as e:
            raise Tier2Failure(f"browser-render-failed: {e}") from e
    if len(html.strip()) < 200:
        raise Tier2Failure("tier2-insufficient-content")
    return Tier2Result(url=url, html=html)
