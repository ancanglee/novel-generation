"""LLM-assisted chapter splitter (called when heuristic confidence < 0.6)."""

from __future__ import annotations

import json
import re

import aioboto3

from worker_ingestion.chapter_splitter import ChapterSplit, merge_short_chapters

_DEFAULT_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"

_SYSTEM = (
    "You are a document structure analyst. Given excerpts from a novel, "
    "identify the regex pattern used for chapter headings. "
    "Respond ONLY with JSON: {\"pattern\": \"<regex>\"} or {\"pattern\": null}."
)


def _sample_excerpts(text: str, window: int = 4096) -> str:
    n = len(text)
    if n <= 3 * window:
        return text
    return "\n\n---\n\n".join(
        [
            text[:window],
            text[n // 2 - window // 2 : n // 2 + window // 2],
            text[-window:],
        ]
    )


async def detect_pattern(text: str, model_id: str = _DEFAULT_MODEL) -> str | None:
    session = aioboto3.Session()
    sample = _sample_excerpts(text)
    async with session.client("bedrock-runtime") as client:
        resp = await client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": f"Sample text:\n{sample}\n\nReturn JSON only."}],
                }
            ],
            system=[{"text": _SYSTEM}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.0},
        )
    try:
        text_out = resp["output"]["message"]["content"][0]["text"]
        data = json.loads(text_out)
        return data.get("pattern")
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


async def split_with_llm(markdown: str, model_id: str = _DEFAULT_MODEL) -> list[ChapterSplit]:
    pattern = await detect_pattern(markdown, model_id=model_id)
    if not pattern:
        return [
            ChapterSplit(idx=1, title="全文", content=markdown.strip(), confidence=0.3)
        ]
    try:
        regex = re.compile(pattern, re.MULTILINE)
    except re.error:
        return [
            ChapterSplit(idx=1, title="全文", content=markdown.strip(), confidence=0.3)
        ]

    matches = list(regex.finditer(markdown))
    if not matches:
        return [
            ChapterSplit(idx=1, title="全文", content=markdown.strip(), confidence=0.3)
        ]

    chapters: list[ChapterSplit] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        chapters.append(
            ChapterSplit(
                idx=i + 1,
                title=m.group(0).strip(),
                content=markdown[start:end].strip(),
                heading_level=2,
                confidence=0.7,
            )
        )
    return merge_short_chapters(chapters)
