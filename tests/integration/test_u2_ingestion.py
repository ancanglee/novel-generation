"""U2 integration smoke tests: sample P0 AC verification."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from worker_ingestion.chapter_splitter import split
from worker_ingestion.parsers import get_parser
from worker_ingestion.parsers.registry import *  # noqa: F401,F403
from worker_ingestion.robots import RobotsDenied, ensure_allowed
from worker_ingestion.url_normalizer import cache_key


class TestUploadAc:
    """US-02-01 upload file AC checks (heuristic-level)."""

    def test_txt_upload_produces_chapters(self):
        parser = get_parser("text/plain")
        raw = ("第一章 开端\n\n" + "句子。" * 300 + "\n\n第二章 发展\n\n" + "句子。" * 300).encode("utf-8")
        parsed = parser.parse(raw, filename="novel.txt")
        chapters = split(parsed.markdown)
        assert len(chapters) == 2
        assert chapters[0].title.startswith("第一章")

    def test_markdown_passthrough_heading_split(self):
        md = "\n\n".join([f"## 章节 {i}\n\n{'内容。' * 200}" for i in range(1, 6)])
        parser = get_parser("text/markdown")
        parsed = parser.parse(md.encode("utf-8"), filename="a.md")
        chapters = split(parsed.markdown)
        assert len(chapters) == 5


class TestCrawlRobotsCompliance:
    """US-02-03 robots.txt disallow → 403 hard reject."""

    def test_robots_denied_raises(self):
        with patch("worker_ingestion.robots._get_parser") as mock:
            parser = mock.return_value
            parser.can_fetch.return_value = False
            with pytest.raises(RobotsDenied):
                ensure_allowed("https://example.com/private")

    def test_robots_allowed_passes(self):
        with patch("worker_ingestion.robots._get_parser") as mock:
            parser = mock.return_value
            parser.can_fetch.return_value = True
            ensure_allowed("https://example.com/public")  # no raise


class TestCacheKey:
    """crawl-cache key semantics (tracking params stripped, deterministic)."""

    def test_tracking_params_do_not_affect_key(self):
        assert cache_key("https://x.com/p?id=1&utm_source=x") == cache_key(
            "https://x.com/p?id=1"
        )

    def test_host_case_insensitive(self):
        assert cache_key("https://X.COM/a") == cache_key("https://x.com/a")
