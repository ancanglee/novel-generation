"""sample_chapters — LLM-adaptive sampling (F2=C) using Haiku 4.5."""

from __future__ import annotations

from typing import Any

from worker_analysis.agents._bedrock import invoke_tool

MIN_SAMPLES = 8
MAX_SAMPLES = 15

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "selected": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "description": "Chapter indices (1-based) chosen for rough read",
        },
        "reasons": {
            "type": "object",
            "description": "Optional per-chapter reason map",
        },
    },
    "required": ["selected"],
}

_SYSTEM = (
    "You pick a small set of chapters that best represent a novel for rough-read analysis. "
    "Prefer first 2 chapters, last 2 chapters, and evenly-spaced plot milestones."
)


async def sample_chapters(
    chapter_titles: list[str],
    total_words: int,
    goal: str = "understand genre / main characters / style",
    *,
    model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0",
) -> list[int]:
    prompt = _build_prompt(chapter_titles, total_words, goal)
    result = await invoke_tool(
        model_id=model_id,
        system_prompt=_SYSTEM,
        user_text=prompt,
        tool_name="record_sampled_chapters",
        tool_schema=_SCHEMA,
        stage="sample_chapters",
    )
    selected = [int(i) for i in result.input.get("selected", []) if 1 <= int(i) <= len(chapter_titles)]
    return _enforce_bounds(selected, len(chapter_titles))


def _build_prompt(titles: list[str], total_words: int, goal: str) -> str:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    return (
        f"Total words: {total_words}. Total chapters: {len(titles)}.\n"
        f"Goal: {goal}.\n\n"
        f"Chapter titles:\n{numbered}\n\n"
        f"Pick {MIN_SAMPLES}-{MAX_SAMPLES} chapter indices that best cover the book."
    )


def _enforce_bounds(selected: list[int], n_chapters: int) -> list[int]:
    must_have = {1, 2} | {max(1, n_chapters - 1), n_chapters}
    combined = sorted({*selected, *must_have})
    if len(combined) > MAX_SAMPLES:
        step = max(1, len(combined) // MAX_SAMPLES)
        combined = combined[::step][:MAX_SAMPLES]
    if len(combined) < MIN_SAMPLES and n_chapters >= MIN_SAMPLES:
        # Fill with evenly-spaced extras
        extras = [
            1 + i * (n_chapters - 1) // (MIN_SAMPLES - 1) for i in range(MIN_SAMPLES)
        ]
        combined = sorted(set(combined) | set(extras))[:MAX_SAMPLES]
    return combined
