"""Two-tier fetch orchestrator (Worker-layer decision per NFR §3.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from novelgen_browser_pool import BrowserPool
from novelgen_obs import emit_metric
from novelgen_types.errors import NovelGenError

from worker_ingestion.fetchers import tier1_http, tier2_browser
from worker_ingestion.robots import RobotsDenied, ensure_allowed


class FetchTier(str, Enum):
    TIER1 = "tier1"
    TIER2 = "tier2"


@dataclass(frozen=True)
class FetchResult:
    url: str
    html: str
    tier: FetchTier


class DowngradeSignal(NovelGenError):
    error_code = "UPSTREAM_DOWNGRADE_REQUIRED"
    http_status = 502


async def fetch_with_downgrade(
    url: str,
    *,
    job_id: str,
    pool: BrowserPool,
    host_metric_dim: str | None = None,
    tier1_timeout: float = 10.0,
    tier2_timeout: int = 60,
) -> FetchResult:
    """Attempt Tier 1 HTTP fetch; fall back to Tier 2 Browser on downgrade conditions.

    robots.txt disallow is a hard rejection and never downgrades.
    """
    ensure_allowed(url)  # raises RobotsDenied → propagates up

    host = host_metric_dim or _host(url)

    try:
        t1 = await tier1_http.fetch(url, timeout=tier1_timeout)
        return FetchResult(url=t1.url, html=t1.html, tier=FetchTier.TIER1)
    except tier1_http.Tier1Failure as e:
        emit_metric(
            "CrawlTierDowngraded",
            1.0,
            dimensions={"Host": host, "Reason": e.reason},
        )

    emit_metric("BrowserSessionCount", 1.0, dimensions={"Host": host})
    t2 = await tier2_browser.fetch(url, job_id=job_id, pool=pool, timeout_seconds=tier2_timeout)
    return FetchResult(url=t2.url, html=t2.html, tier=FetchTier.TIER2)


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc or "unknown"


__all__ = ["DowngradeSignal", "FetchResult", "FetchTier", "RobotsDenied", "fetch_with_downgrade"]
