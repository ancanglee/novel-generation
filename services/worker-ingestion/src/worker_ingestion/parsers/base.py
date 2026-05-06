"""Parser protocol + registry keyed by MIME type."""

from __future__ import annotations

import hashlib
from typing import Protocol

from pydantic import BaseModel, Field

from novelgen_types.errors import NovelGenError


class ParserError(NovelGenError):
    error_code = "UPSTREAM_PARSE_FAILED"
    http_status = 422


class ParsedDocument(BaseModel):
    title: str | None = None
    author: str | None = None
    markdown: str
    word_count: int = 0
    sha256: str = ""
    warnings: list[str] = Field(default_factory=list)


class DocumentParser(Protocol):
    mime_types: tuple[str, ...]

    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument: ...


_REGISTRY: dict[str, DocumentParser] = {}


def register(parser: DocumentParser) -> DocumentParser:
    for mt in parser.mime_types:
        _REGISTRY[mt] = parser
    return parser


def get_parser(mime_type: str) -> DocumentParser:
    parser = _REGISTRY.get(mime_type)
    if parser is None:
        raise ParserError(f"unsupported MIME type: {mime_type}", mime_type=mime_type)
    return parser


def finalize(markdown: str, title: str | None = None, author: str | None = None) -> ParsedDocument:
    body = markdown.strip()
    return ParsedDocument(
        title=title,
        author=author,
        markdown=body,
        word_count=len(body),
        sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )
