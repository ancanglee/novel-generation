"""ctext.org search (simple HTML endpoint)."""

from __future__ import annotations

import httpx
from lxml import html as lxml_html

from worker_ingestion.search.base import SearchResult, SearchSourceId


class CtextSource:
    source_id = SearchSourceId.CTEXT

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://ctext.org/searchbooks.pl",
                    params={"if": "en", "searchu": query},
                )
                resp.raise_for_status()
        except httpx.HTTPError:
            return []

        try:
            doc = lxml_html.fromstring(resp.text)
        except Exception:
            return []

        results: list[SearchResult] = []
        for a in doc.xpath("//a[contains(@href, '/')]")[: limit * 3]:
            href = a.get("href") or ""
            text = (a.text_content() or "").strip()
            if not href or not text or "searchbooks" in href:
                continue
            url = href if href.startswith("http") else f"https://ctext.org/{href.lstrip('/')}"
            results.append(
                SearchResult(
                    source=self.source_id,
                    title=text,
                    url=url,
                    language="zh",
                    copyright_warning=False,
                )
            )
            if len(results) >= limit:
                break
        return results
