"""DOCX parser using python-docx."""

from __future__ import annotations

import io

from docx import Document

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register


def _paragraph_to_md(para) -> str:
    style = (para.style.name or "").lower()
    text = para.text.strip()
    if not text:
        return ""
    if "heading 1" in style:
        return f"# {text}"
    if "heading 2" in style:
        return f"## {text}"
    if "heading 3" in style:
        return f"### {text}"
    return text


class DocxParser:
    mime_types = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        try:
            doc = Document(io.BytesIO(content))
        except Exception as e:
            raise ParserError(f"docx parse failed: {e}") from e

        lines = [line for para in doc.paragraphs if (line := _paragraph_to_md(para))]
        markdown = "\n\n".join(lines)

        title = None
        core = doc.core_properties
        if core.title:
            title = core.title
        elif filename:
            title = filename.rsplit(".", 1)[0]

        return finalize(markdown, title=title, author=core.author or None)


register(DocxParser())
