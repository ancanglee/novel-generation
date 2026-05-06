"""Aggregator tests with fake sources."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from worker_ingestion.search.aggregator import SearchAggregator, _dedupe
from worker_ingestion.search.base import SearchResult, SearchSourceId


class _FakeSource:
    def __init__(self, source_id: SearchSourceId, results: list[SearchResult]) -> None:
        self.source_id = source_id
        self._results = results
        self.search = AsyncMock(return_value=results)


@pytest.mark.asyncio
async def test_two_phase_callbacks_fire_in_order():
    order: list[str] = []

    async def on_a(results):
        order.append(f"a:{len(results)}")

    async def on_b(results):
        order.append(f"b:{len(results)}")

    agg = SearchAggregator()
    # Short-circuit: monkey-patch _a/_b with fakes
    agg._a = [_FakeSource(SearchSourceId.GUTENBERG, [_mk("G", "x")])]
    agg._b = [_FakeSource(SearchSourceId.BAIDU, [_mk("B", "y", warning=True)])]

    result = await agg.search("红楼梦", on_group_a_ready=on_a, on_group_b_ready=on_b)

    assert order == ["a:1", "b:1"]
    assert len(result.group_a) == 1
    assert len(result.group_b) == 1
    assert result.group_b[0].copyright_warning is True


def test_dedupe_by_normalized_title_author():
    rs = [
        _mk("红楼梦", "曹雪芹"),
        _mk("  红楼梦  ", "曹雪芹"),
        _mk("水浒传", "施耐庵"),
    ]
    out = _dedupe(rs)
    assert len(out) == 2


def _mk(title: str, url_suffix: str, warning: bool = False) -> SearchResult:
    return SearchResult(
        source=SearchSourceId.GUTENBERG,
        title=title,
        url=f"https://example.com/{url_suffix}",
        copyright_warning=warning,
    )
