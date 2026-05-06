"""Orchestrator decision tests (robots / Tier1 happy / Tier1 fail → Tier2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from worker_ingestion.fetchers import orchestrator, tier1_http, tier2_browser
from worker_ingestion.robots import RobotsDenied


@pytest.mark.asyncio
async def test_robots_disallow_raises_and_skips_downgrade():
    with patch("worker_ingestion.fetchers.orchestrator.ensure_allowed", side_effect=RobotsDenied("denied")):
        with pytest.raises(RobotsDenied):
            await orchestrator.fetch_with_downgrade("https://blocked.example/x", job_id="j1", pool=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_tier1_success_returns_tier1():
    with patch("worker_ingestion.fetchers.orchestrator.ensure_allowed", return_value=None):
        with patch.object(
            tier1_http,
            "fetch",
            new=AsyncMock(
                return_value=tier1_http.Tier1Result(
                    status_code=200, url="https://x.example/a", html="<html><body>long body " + "a" * 500 + "</body></html>", headers={}
                )
            ),
        ):
            result = await orchestrator.fetch_with_downgrade(
                "https://x.example/a", job_id="j1", pool=None  # type: ignore[arg-type]
            )
            assert result.tier == orchestrator.FetchTier.TIER1


@pytest.mark.asyncio
async def test_tier1_blocked_downgrades_to_tier2():
    with patch("worker_ingestion.fetchers.orchestrator.ensure_allowed", return_value=None):
        with patch.object(
            tier1_http, "fetch",
            new=AsyncMock(side_effect=tier1_http.Tier1Failure("status-blocked", status=403)),
        ):
            with patch.object(
                tier2_browser,
                "fetch",
                new=AsyncMock(return_value=tier2_browser.Tier2Result(url="https://x.example/a", html="rendered " + "b" * 500)),
            ):
                result = await orchestrator.fetch_with_downgrade(
                    "https://x.example/a", job_id="j1", pool=None  # type: ignore[arg-type]
                )
                assert result.tier == orchestrator.FetchTier.TIER2


@pytest.mark.asyncio
async def test_tier1_js_only_downgrades():
    with patch("worker_ingestion.fetchers.orchestrator.ensure_allowed", return_value=None):
        with patch.object(
            tier1_http, "fetch", new=AsyncMock(side_effect=tier1_http.Tier1Failure("js-only"))
        ):
            with patch.object(
                tier2_browser,
                "fetch",
                new=AsyncMock(return_value=tier2_browser.Tier2Result(url="https://x.example/a", html="c" * 500)),
            ):
                result = await orchestrator.fetch_with_downgrade(
                    "https://x.example/a", job_id="j1", pool=None  # type: ignore[arg-type]
                )
                assert result.tier == orchestrator.FetchTier.TIER2
