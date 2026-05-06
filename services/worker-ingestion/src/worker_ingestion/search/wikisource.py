"""Chinese Wikisource search via MediaWiki API."""

from __future__ import annotations

import httpx

from worker_ingestion.search.base import SearchResult, SearchSourceId

_ENDPOINT = "https://zh.wikisource.org/w/api.php"


class WikisourceSource:
    source_id = SearchSourceId.WIKISOURCE

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    _ENDPOINT,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": limit,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            return []

        results: list[SearchResult] = []
        for hit in data.get("query", {}).get("search", [])[:limit]:
            title = hit.get("title") or ""
            snippet = (hit.get("snippet") or "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
            url = f"https://zh.wikisource.org/wiki/{title.replace(' ', '_')}"
            results.append(
                SearchResult(
                    source=self.source_id,
                    title=title,
                    url=url,
                    language="zh",
                    snippet=snippet[:200],
                    copyright_warning=False,
                )
            )
        return results
