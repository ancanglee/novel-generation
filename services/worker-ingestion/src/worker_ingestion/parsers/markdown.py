"""Markdown parser (pass-through)."""

from __future__ import annotations

from worker_ingestion.parsers.base import ParsedDocument, finalize, register


class MarkdownParser:
    mime_types = ("text/markdown", "text/x-markdown")

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        title = filename.rsplit(".", 1)[0] if filename else None
        return finalize(text, title=title)


register(MarkdownParser())
