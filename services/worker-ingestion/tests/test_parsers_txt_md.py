"""Smoke tests for the simplest parsers that don't need fixture files."""

from __future__ import annotations

import pytest
from worker_ingestion.parsers import get_parser
from worker_ingestion.parsers.base import ParserError
from worker_ingestion.parsers.registry import *  # noqa: F403 ensure all parsers registered


def test_txt_parser_detects_encoding():
    parser = get_parser("text/plain")
    result = parser.parse("你好，世界".encode("gb18030"), filename="novel.txt")
    assert "你好" in result.markdown
    assert result.title == "novel"
    assert result.word_count > 0
    assert result.sha256


def test_txt_parser_rejects_empty():
    parser = get_parser("text/plain")
    with pytest.raises(ParserError):
        parser.parse(b"")


def test_markdown_parser_passthrough():
    parser = get_parser("text/markdown")
    md = "# Hello\n\nbody text"
    result = parser.parse(md.encode("utf-8"), filename="story.md")
    assert result.markdown == md
    assert result.title == "story"


def test_unsupported_mime_type_raises():
    with pytest.raises(ParserError):
        get_parser("application/x-binary")
