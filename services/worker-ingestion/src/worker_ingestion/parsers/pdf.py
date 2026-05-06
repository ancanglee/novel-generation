"""PDF parser with pypdf primary + pdfplumber fallback."""

from __future__ import annotations

import io

import pdfplumber
from pypdf import PdfReader

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register


def _extract_with_pypdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p for p in parts if p.strip())


def _extract_with_pdfplumber(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        parts = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(p for p in parts if p.strip())


class PdfParser:
    mime_types = ("application/pdf",)

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        try:
            text = _extract_with_pypdf(content)
        except Exception:
            text = ""
        if len(text.strip()) < 100:
            try:
                text = _extract_with_pdfplumber(content)
            except Exception as e:
                raise ParserError(f"pdf parse failed: {e}") from e
        if not text.strip():
            raise ParserError("pdf yielded no extractable text (scanned PDF not supported in V1)")
        title = filename.rsplit(".", 1)[0] if filename else None
        return finalize(text, title=title)


register(PdfParser())
