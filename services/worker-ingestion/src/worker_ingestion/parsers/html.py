"""HTML parser using trafilatura (also used by URL fetchers)."""

from __future__ import annotations

import trafilatura

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register


class HtmlParser:
    mime_types = ("text/html", "application/xhtml+xml")

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        extracted = trafilatura.extract(
            text,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="markdown",
        )
        if not extracted or len(extracted.strip()) < 50:
            raise ParserError("html yielded insufficient content")
        metadata = trafilatura.extract_metadata(text)
        title = metadata.title if metadata else None
        author = metadata.author if metadata else None
        return finalize(extracted, title=title, author=author)


register(HtmlParser())
