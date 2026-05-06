"""EPUB parser: extract chapters with ebooklib, produce Markdown."""

from __future__ import annotations

import io

from ebooklib import epub
from lxml import html as lxml_html

from worker_ingestion.parsers.base import ParsedDocument, ParserError, finalize, register


def _html_to_text(content: bytes) -> str:
    try:
        doc = lxml_html.fromstring(content)
    except (ValueError, lxml_html.etree.ParserError):
        return ""
    for tag in doc.xpath("//script | //style"):
        tag.getparent().remove(tag)
    return doc.text_content()


class EpubParser:
    mime_types = ("application/epub+zip",)

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument:
        try:
            book = epub.read_epub(io.BytesIO(content))
        except Exception as e:
            raise ParserError(f"epub parse failed: {e}") from e

        title = next(iter(book.get_metadata("DC", "title")), (None,))[0]
        author = next(iter(book.get_metadata("DC", "creator")), (None,))[0]

        chunks: list[str] = []
        for item in book.get_items_of_type(epub.ITEM_DOCUMENT):
            text = _html_to_text(item.get_content()).strip()
            if not text:
                continue
            chunks.append(text)

        markdown = "\n\n".join(chunks)
        return finalize(markdown, title=title, author=author)


register(EpubParser())
