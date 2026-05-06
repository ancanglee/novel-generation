"""Baidu / Bing generic search engine sources.

Scraping SERPs is brittle and often blocked; in practice Tier 1 HTML will fail and the
orchestrator will downgrade to Tier 2 AgentCore Browser. Results flagged copyright_warning=True
so the UI warns the user per R4.3.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx
from lxml import html as lxml_html

from worker_ingestion.search.base import SearchResult, SearchSourceId


class BaiduSource:
    source_id = SearchSourceId.BAIDU

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await _scrape_generic(
            url=f"https://www.baidu.com/s?wd={quote(query)}",
            xpath="//h3/a[@href]",
            limit=limit,
            source_id=self.source_id,
        )


class BingSource:
    source_id = SearchSourceId.BING

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        return await _scrape_generic(
            url=f"https://www.bing.com/search?q={quote(query)}",
            xpath="//li[@class='b_algo']//h2/a[@href]",
            limit=limit,
            source_id=self.source_id,
        )


async def _scrape_generic(
    url: str, xpath: str, limit: int, source_id: SearchSourceId
) -> list[SearchResult]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "NovelGenBot/0.1 (+https://novelgen.example.com/bot)",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            if resp.status_code >= 400:
                return []  # Tier 1 failed; orchestrator would retry via Tier 2 on URL-level fetch
    except httpx.HTTPError:
        return []

    try:
        doc = lxml_html.fromstring(resp.text)
    except Exception:
        return []

    results: list[SearchResult] = []
    for a in doc.xpath(xpath)[: limit * 2]:
        href = a.get("href") or ""
        title = (a.text_content() or "").strip()
        if not href or not title or not href.startswith("http"):
            continue
        results.append(
            SearchResult(
                source=source_id,
                title=title,
                url=href,
                language="zh",
                copyright_warning=True,  # flag for UI
            )
        )
        if len(results) >= limit:
            break
    return results
