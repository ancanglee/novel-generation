"""Project Gutenberg search (Gutendex JSON API)."""

from __future__ import annotations

import httpx

from worker_ingestion.search.base import SearchResult, SearchSourceId

_ENDPOINT = "https://gutendex.com/books"


class GutenbergSource:
    source_id = SearchSourceId.GUTENBERG

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_ENDPOINT, params={"search": query, "page_size": limit})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError:
            return []

        results: list[SearchResult] = []
        for book in data.get("results", [])[:limit]:
            title = book.get("title") or ""
            authors = ", ".join(a.get("name", "") for a in book.get("authors", []))
            formats = book.get("formats", {})
            # Prefer plaintext UTF-8, then epub
            url = (
                formats.get("text/plain; charset=utf-8")
                or formats.get("text/plain")
                or formats.get("application/epub+zip")
                or next(iter(formats.values()), "")
            )
            if not url:
                continue
            languages = book.get("languages") or ["en"]
            results.append(
                SearchResult(
                    source=self.source_id,
                    title=title,
                    author=authors or None,
                    url=url,
                    format_hint="txt" if "text/plain" in url else "epub",
                    language=languages[0],
                    snippet="",
                    copyright_warning=False,
                )
            )
        return results
