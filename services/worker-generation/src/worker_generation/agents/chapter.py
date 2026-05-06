"""ChapterAgent — streams a chapter via Bedrock converse_stream, with cancel checks."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from uuid import UUID

from novelgen_obs import emit_metric, get_logger

from worker_generation.agents._bedrock_stream import converse_stream
from worker_generation.cancel_cache import CancelCache
from worker_generation.event_publisher import EventPublisher, GenerationEvent
from worker_generation.mode import Mode, prompt_name_for
from worker_generation.prompts import load_prompt
from worker_generation.style_injection import (
    StyleVector,
    build_memory_block,
    build_previous_chapter_block,
    build_style_block,
)

log = get_logger("worker-generation.chapter")


async def generate_chapter_stream(
    *,
    team_id: UUID,
    job_id: UUID,
    generation_id: UUID,
    chapter_idx: int,
    mode: Mode,
    style_vector: StyleVector,
    style_reference_excerpts: list[str],
    memory_facts: list[str],
    previous_chapter_tail: str,
    outline_item_summary: str,
    target_words: int,
    cancel_cache: CancelCache,
    publisher: EventPublisher,
    model_id: str = "anthropic.claude-sonnet-4-7-v1:0",
    event_id_start: int = 0,
) -> AsyncIterator[str]:
    """Stream chapter text_deltas. Publishes EventBridge events per token and on completion.

    Yields the accumulated text segments so callers can also write to S3 incrementally.
    """
    system_prompt = _build_system_prompt(
        mode=mode,
        style_vector=style_vector,
        style_reference_excerpts=style_reference_excerpts,
        memory_facts=memory_facts,
        previous_chapter_tail=previous_chapter_tail,
    )
    user_text = (
        f"Chapter {chapter_idx}\nTarget words: {target_words}\n\n"
        f"Chapter outline summary:\n{outline_item_summary}\n\n"
        f"Please write this chapter now."
    )

    await publisher.publish(
        GenerationEvent(
            detail_type="generation.chapter.streaming",
            generation_id=generation_id, team_id=team_id,
            chapter_idx=chapter_idx, event_id=f"{generation_id}:{chapter_idx}:start",
            payload={"phase": "start"},
        )
    )

    started = time.monotonic()
    ttft_recorded = False
    event_counter = event_id_start

    async for event in converse_stream(
        model_id=model_id, system_prompt=system_prompt, user_text=user_text
    ):
        if "contentBlockDelta" in event:
            text = event["contentBlockDelta"].get("delta", {}).get("text", "")
            if not text:
                continue

            if not ttft_recorded:
                emit_metric("ChapterTTFTMs", (time.monotonic() - started) * 1000.0)
                ttft_recorded = True

            if await cancel_cache.is_canceled(team_id, job_id):
                log.info("chapter canceled mid-stream", extra={"generation_id": str(generation_id), "chapter_idx": chapter_idx})
                await publisher.publish(
                    GenerationEvent(
                        detail_type="generation.chapter.canceled",
                        generation_id=generation_id, team_id=team_id,
                        chapter_idx=chapter_idx,
                        event_id=f"{generation_id}:{chapter_idx}:canceled",
                        payload={},
                    )
                )
                return

            event_counter += 1
            await publisher.publish(
                GenerationEvent(
                    detail_type="generation.chapter.streaming",
                    generation_id=generation_id, team_id=team_id,
                    chapter_idx=chapter_idx,
                    event_id=f"{generation_id}:{chapter_idx}:{event_counter}",
                    payload={"text_delta": text},
                )
            )
            yield text

    total_ms = (time.monotonic() - started) * 1000.0
    emit_metric("ChapterGenerationMs", total_ms)

    await publisher.publish(
        GenerationEvent(
            detail_type="generation.chapter.completed",
            generation_id=generation_id, team_id=team_id,
            chapter_idx=chapter_idx,
            event_id=f"{generation_id}:{chapter_idx}:complete",
            payload={"duration_ms": total_ms},
        )
    )


def _build_system_prompt(
    *, mode: Mode, style_vector: StyleVector, style_reference_excerpts: list[str],
    memory_facts: list[str], previous_chapter_tail: str,
) -> str:
    mode_block = load_prompt(prompt_name_for(mode))
    style_block = build_style_block(style_vector, style_reference_excerpts)
    memory_block = build_memory_block(memory_facts)
    prev_block = build_previous_chapter_block(previous_chapter_tail)
    return f"{mode_block}\n\n{style_block}\n\n{memory_block}\n\n{prev_block}"
