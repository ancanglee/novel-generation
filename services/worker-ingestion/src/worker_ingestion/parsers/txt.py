"""Plain-text parser with automatic encoding detection."""

from __future__ import annotations

import chardet

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register


class TxtParser:
    mime_types = ("text/plain",)

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        if not content:
            raise ParserError("empty file")
        detection = chardet.detect(content) or {}
        encoding = detection.get("encoding") or "utf-8"
        try:
            text = content.decode(encoding, errors="replace")
        except LookupError:
            text = content.decode("utf-8", errors="replace")
        title = filename.rsplit(".", 1)[0] if filename else None
        return finalize(text, title=title)


register(TxtParser())
