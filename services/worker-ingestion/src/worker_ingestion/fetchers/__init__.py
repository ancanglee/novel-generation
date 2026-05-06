"""Two-tier fetchers: HTTP (fast) with AgentCore Browser fallback."""

from worker_ingestion.fetchers.orchestrator import (
    DowngradeSignal,
    FetchResult,
    fetch_with_downgrade,
)

__all__ = ["DowngradeSignal", "FetchResult", "fetch_with_downgrade"]
