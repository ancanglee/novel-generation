"""Search aggregator: group-parallel execution, two-phase SSE emission (D2=C)."""

from __future__ import annotations

import asyncio
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from worker_ingestion.search.base import SearchResult, SearchSource, SearchSourceId
from worker_ingestion.search.ctext import CtextSource
from worker_ingestion.search.gutenberg import GutenbergSource
from worker_ingestion.search.search_engines import BaiduSource, BingSource
from worker_ingestion.search.wikisource import WikisourceSource

GROUP_A: tuple[type[SearchSource], ...] = (GutenbergSource, CtextSource, WikisourceSource)
GROUP_B: tuple[type[SearchSource], ...] = (BaiduSource, BingSource)


@dataclass(frozen=True)
class GroupedResults:
    group_a: list[SearchResult]
    group_b: list[SearchResult]


class SearchAggregator:
    """Run Group A (public-domain APIs) in parallel then Group B (search engines).

    `on_group_a_ready` / `on_group_b_ready` callbacks let the orchestrator push
    intermediate results to the UI via SSE before aggregation completes.
    """

    def __init__(
        self,
        sources_a: tuple[type[SearchSource], ...] = GROUP_A,
        sources_b: tuple[type[SearchSource], ...] = GROUP_B,
    ) -> None:
        self._a = [cls() for cls in sources_a]
        self._b = [cls() for cls in sources_b]

    async def search(
        self,
        query: str,
        limit_per_source: int = 10,
        on_group_a_ready: Callable[[list[SearchResult]], Awaitable[None]] | None = None,
        on_group_b_ready: Callable[[list[SearchResult]], Awaitable[None]] | None = None,
    ) -> GroupedResults:
        group_a = await self._run_group(self._a, query, limit_per_source)
        group_a = _dedupe(group_a)
        if on_group_a_ready:
            await on_group_a_ready(group_a)

        group_b = await self._run_group(self._b, query, limit_per_source)
        group_b = _dedupe(group_b)
        if on_group_b_ready:
            await on_group_b_ready(group_b)

        return GroupedResults(group_a=group_a, group_b=group_b)

    @staticmethod
    async def _run_group(
        sources: list[SearchSource], query: str, limit: int
    ) -> list[SearchResult]:
        coros = [s.search(query, limit=limit) for s in sources]
        returned = await asyncio.gather(*coros, return_exceptions=True)
        merged: list[SearchResult] = []
        for item in returned:
            if isinstance(item, Exception):
                continue
            merged.extend(item)
        return merged


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().lower()


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    seen: set[tuple[str, str]] = set()
    out: list[SearchResult] = []
    for r in results:
        key = (_normalize(r.title), _normalize(r.author or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


__all__ = ["GROUP_A", "GROUP_B", "GroupedResults", "SearchAggregator", "SearchSourceId"]
