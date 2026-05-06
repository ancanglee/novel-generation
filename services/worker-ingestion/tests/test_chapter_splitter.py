"""Heuristic chapter splitter tests."""

from __future__ import annotations

from worker_ingestion.chapter_splitter import split, split_heuristic


def _fake_chinese_novel() -> str:
    chapters = []
    for i in range(1, 11):
        body = ("句子。" * 200) + "\n"
        chapters.append(f"第{i}章 测试\n\n{body}")
    return "\n".join(chapters)


def _fake_english_novel() -> str:
    chapters = []
    for i in range(1, 8):
        body = ("A sentence. " * 200) + "\n"
        chapters.append(f"Chapter {i}\n\n{body}")
    return "\n".join(chapters)


def test_splits_chinese_chapters():
    chapters, conf = split_heuristic(_fake_chinese_novel())
    assert len(chapters) == 10
    assert conf > 0.5
    assert chapters[0].title.startswith("第1章")


def test_splits_english_chapters():
    chapters, _conf = split_heuristic(_fake_english_novel())
    assert len(chapters) == 7
    assert chapters[3].title.startswith("Chapter")


def test_unstructured_single_chapter_fallback():
    text = "Just a short blob of prose without any recognizable headings."
    result = split(text)
    assert len(result) == 1
    assert result[0].title == "全文"


def test_md_h1_headings():
    md = "\n".join([f"# Part {i}\n\n{'word ' * 200}" for i in range(1, 7)])
    chapters, _conf = split_heuristic(md)
    assert len(chapters) == 6
    assert chapters[0].heading_level == 1
