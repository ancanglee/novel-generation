"""Chapter splitter: heuristic regex first, LLM fallback when confidence < 0.6."""

from __future__ import annotations

import itertools
import math
import re
import statistics
from dataclasses import dataclass

from pydantic import BaseModel, Field


class ChapterSplit(BaseModel):
    idx: int = Field(ge=1)
    title: str
    content: str
    heading_level: int = 0
    confidence: float = 1.0


@dataclass(frozen=True)
class HeuristicPattern:
    name: str
    regex: re.Pattern[str]
    heading_level: int


_PATTERNS: tuple[HeuristicPattern, ...] = (
    HeuristicPattern(
        name="md-h1",
        regex=re.compile(r"^#\s+(?P<title>.+)$", re.MULTILINE),
        heading_level=1,
    ),
    HeuristicPattern(
        name="md-h2",
        regex=re.compile(r"^##\s+(?P<title>.+)$", re.MULTILINE),
        heading_level=2,
    ),
    HeuristicPattern(
        name="chinese-chapter",
        regex=re.compile(
            r"^(?P<title>第\s*[一二三四五六七八九十百千万零〇\d]+\s*[章回节卷篇].*)$",
            re.MULTILINE,
        ),
        heading_level=2,
    ),
    HeuristicPattern(
        name="english-chapter",
        regex=re.compile(
            r"^(?P<title>(?:Chapter|CHAPTER|Part|PART)\s+[\dIVXLCDM]+.*)$",
            re.MULTILINE,
        ),
        heading_level=2,
    ),
)


def split_heuristic(markdown: str) -> tuple[list[ChapterSplit], float]:
    """Try each pattern; return the first one yielding ≥ 5 evenly-spaced matches."""
    best: tuple[list[ChapterSplit], float] = ([], 0.0)
    for pattern in _PATTERNS:
        matches = list(pattern.regex.finditer(markdown))
        if len(matches) < 2:
            continue
        positions = [m.start() for m in matches]
        gaps = [b - a for a, b in itertools.pairwise(positions)]
        if not gaps:
            continue
        mean_gap = statistics.mean(gaps)
        stdev_gap = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
        uniformity = 1.0 - min(1.0, (stdev_gap / mean_gap) if mean_gap else 1.0)
        count_score = min(1.0, math.log1p(len(matches)) / math.log1p(10))
        confidence = 0.4 * uniformity + 0.6 * count_score

        chapters: list[ChapterSplit] = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            body = markdown[start:end].strip()
            title = m.group("title").strip()
            chapters.append(
                ChapterSplit(
                    idx=i + 1,
                    title=title,
                    content=body,
                    heading_level=pattern.heading_level,
                    confidence=confidence,
                )
            )
        if confidence > best[1]:
            best = (chapters, confidence)

    return best


def merge_short_chapters(chapters: list[ChapterSplit], min_chars: int = 200) -> list[ChapterSplit]:
    """Merge chapters with body shorter than min_chars into the prior chapter (TOC guard)."""
    if not chapters:
        return chapters
    merged: list[ChapterSplit] = [chapters[0]]
    for ch in chapters[1:]:
        if len(ch.content) < min_chars and merged:
            prev = merged[-1]
            merged[-1] = prev.model_copy(
                update={"content": prev.content + "\n\n" + ch.title + "\n\n" + ch.content}
            )
        else:
            merged.append(ch)
    # Re-index
    return [c.model_copy(update={"idx": i + 1}) for i, c in enumerate(merged)]


def split(markdown: str, confidence_floor: float = 0.6) -> list[ChapterSplit]:
    """Produce chapter splits; caller invokes LLM fallback when top confidence < floor."""
    chapters, confidence = split_heuristic(markdown)
    if confidence < confidence_floor or not chapters:
        # Single-chapter fallback; the pipeline will invoke the LLM splitter separately.
        return [
            ChapterSplit(
                idx=1,
                title="全文",
                content=markdown.strip(),
                heading_level=0,
                confidence=confidence,
            )
        ]
    return merge_short_chapters(chapters)
