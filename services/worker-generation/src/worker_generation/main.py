"""Worker main: dual-queue SQS consumer (generation + review) with msg-kind routing."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any
from uuid import UUID

import aioboto3
from novelgen_obs import get_logger, set_request_id
from novelgen_storage import DynamoDBAdapter, S3Adapter, build_s3_prefix, build_team_pk

from worker_generation.agents import (
    generate_chapter_stream,
    generate_outline,
    review_outline_changes,
    self_critique_chapter,
)
from worker_generation.cancel_cache import CancelCache
from worker_generation.event_publisher import EventPublisher
from worker_generation.mode import Mode
from worker_generation.style_injection import StyleVector

log = get_logger("worker-generation")

GENERATION_QUEUE_URL = os.environ["GENERATION_QUEUE_URL"]
REVIEW_QUEUE_URL = os.environ["REVIEW_QUEUE_URL"]
NOVELS_BUCKET = os.environ["NOVELS_BUCKET"]
TENANCY_TABLE = os.environ["TENANCY_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
REGION = os.environ.get("AWS_REGION", "us-east-1")


class _DdbJobReader:
    def __init__(self, jobs_table: DynamoDBAdapter) -> None:
        self._ddb = jobs_table

    async def is_canceled(self, team_id: UUID, job_id: UUID) -> bool:
        item = await self._ddb.get(
            team_id=team_id,
            pk=build_team_pk(team_id),
            sk=f"JOB#{job_id}",
        )
        return bool(item and item.get("cancel_requested"))


async def _run() -> None:
    session = aioboto3.Session()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    jobs_table = DynamoDBAdapter(JOBS_TABLE, region=REGION)
    tenancy = DynamoDBAdapter(TENANCY_TABLE, region=REGION)
    s3 = S3Adapter(NOVELS_BUCKET, region=REGION)
    cancel_cache = CancelCache(_DdbJobReader(jobs_table))
    publisher = EventPublisher(region=REGION)

    async with session.client("sqs", region_name=REGION) as sqs, session.client(
        "stepfunctions", region_name=REGION
    ) as sfn:
        log.info("worker-generation started")
        while not stop_event.is_set():
            await asyncio.gather(
                _poll(sqs, sfn, GENERATION_QUEUE_URL, _handle_generation_msg,
                      s3, tenancy, jobs_table, cancel_cache, publisher),
                _poll(sqs, sfn, REVIEW_QUEUE_URL, _handle_review_msg,
                      s3, tenancy, jobs_table, cancel_cache, publisher),
            )


async def _poll(sqs, sfn, queue_url: str, handler, *args) -> None:
    resp = await sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10, VisibilityTimeout=1200
    )
    for msg in resp.get("Messages", []):
        try:
            await handler(sqs, sfn, queue_url, msg, *args)
        except Exception:
            log.exception("message handling failed")


async def _handle_generation_msg(
    sqs, sfn, queue_url, msg, s3, tenancy, jobs_table, cancel_cache, publisher
) -> None:
    body = json.loads(msg["Body"])
    kind = body.get("kind", "")
    task = body.get("task") or {}
    task_token = body.get("taskToken")
    set_request_id(msg.get("MessageId", ""))

    try:
        if kind == "outline":
            await _do_outline(task, s3, tenancy)
        elif kind == "chapter":
            await _do_chapter(task, s3, tenancy, jobs_table, cancel_cache, publisher)
        else:
            log.warning("unknown generation kind", extra={"kind": kind})

        if task_token:
            await sfn.send_task_success(taskToken=task_token, output="{}")
        await sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
    except Exception as e:
        log.exception("generation task failed")
        if task_token:
            await sfn.send_task_failure(taskToken=task_token, error=type(e).__name__, cause=str(e)[:1024])


async def _handle_review_msg(
    sqs, sfn, queue_url, msg, s3, tenancy, jobs_table, cancel_cache, publisher
) -> None:
    body = json.loads(msg["Body"])
    task = body.get("task") or {}
    await _do_outline_review(task, s3, tenancy)
    await sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])


# ------------- task implementations ------------------------------------

async def _do_outline(task: dict[str, Any], s3: S3Adapter, tenancy: DynamoDBAdapter) -> None:
    team_id = UUID(task["team_id"])
    generation_id = UUID(task["generation_id"])
    mode = task.get("mode", "clean_room")
    target_chapter_count = int(task.get("target_chapter_count", 50))
    target_words = int(task.get("target_words_per_chapter", 3000))

    outline = await generate_outline(
        analysis_report_text=task.get("analysis_report_text", ""),
        mode=mode,
        style_vector_text=task.get("style_vector_text", ""),
        target_chapter_count=target_chapter_count,
        target_words_per_chapter=target_words,
    )

    key = f"{build_s3_prefix(team_id)}generations/{generation_id}/outline.v1.json"
    await s3.put_object(
        team_id, key, json.dumps(outline, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
    await tenancy.update(
        team_id=team_id,
        pk=build_team_pk(team_id),
        sk=f"GEN#{generation_id}",
        update_expression="SET outline_s3_key = :k, #s = :st, updated_at = :u",
        expression_names={"#s": "status"},
        expression_values={
            ":k": key, ":st": "OUTLINE_READY", ":u": _now(),
        },
    )


async def _do_chapter(
    task: dict[str, Any], s3: S3Adapter, tenancy: DynamoDBAdapter,
    jobs_table: DynamoDBAdapter, cancel_cache: CancelCache, publisher: EventPublisher,
) -> None:
    team_id = UUID(task["team_id"])
    generation_id = UUID(task["generation_id"])
    chapter_idx = int(task["chapter_idx"])
    job_id = UUID(task["job_id"])
    mode = Mode(task.get("mode", "clean_room"))

    # Read generation context (populated by load-generation-context Lambda)
    ctx = await jobs_table.get(
        team_id=team_id, pk=build_team_pk(team_id), sk=f"GEN_CONTEXT#{generation_id}"
    ) or {}
    style_vector = StyleVector(**ctx.get("style_vector", {}))
    style_refs: list[str] = ctx.get("style_reference_excerpts", [])

    outline = ctx.get("outline_items", [])
    item = outline[chapter_idx - 1] if chapter_idx - 1 < len(outline) else {}

    # Read previous chapter tail from S3 (last 500 chars), if any
    prev_tail = ""
    if chapter_idx > 1:
        prev_key = f"{build_s3_prefix(team_id)}generations/{generation_id}/chapters/{chapter_idx - 1:05d}.md"
        try:
            prev_tail = (await s3.get_object(team_id, prev_key)).decode("utf-8", errors="replace")
        except Exception:
            prev_tail = ""

    chunks: list[str] = []
    async for delta in generate_chapter_stream(
        team_id=team_id, job_id=job_id, generation_id=generation_id, chapter_idx=chapter_idx,
        mode=mode, style_vector=style_vector,
        style_reference_excerpts=style_refs,
        memory_facts=ctx.get("recent_facts", []),
        previous_chapter_tail=prev_tail,
        outline_item_summary=item.get("summary", ""),
        target_words=int(item.get("target_words", 3000)),
        cancel_cache=cancel_cache, publisher=publisher,
    ):
        chunks.append(delta)

    chapter_text = "".join(chunks)
    if not chapter_text:
        return  # canceled

    key = f"{build_s3_prefix(team_id)}generations/{generation_id}/chapters/{chapter_idx:05d}.md"
    await s3.put_object(team_id, key, chapter_text.encode("utf-8"), content_type="text/markdown")
    await tenancy.put(
        team_id=team_id,
        item={
            "pk": build_team_pk(team_id),
            "sk": f"GEN_CHAPTER#{generation_id}#{chapter_idx:05d}",
            "generation_id": str(generation_id),
            "chapter_idx": chapter_idx,
            "status": "GENERATED",
            "content_s3_key": key,
            "word_count": len(chapter_text),
            "generated_at": _now(),
        },
    )


async def _do_outline_review(task: dict[str, Any], s3: S3Adapter, tenancy: DynamoDBAdapter) -> None:
    team_id = UUID(task["team_id"])
    generation_id = UUID(task["generation_id"])

    old_key = task["old_outline_key"]
    new_key = task["new_outline_key"]
    old = json.loads((await s3.get_object(team_id, old_key)).decode("utf-8"))
    new = json.loads((await s3.get_object(team_id, new_key)).decode("utf-8"))

    advice = await review_outline_changes(
        outline_old=old, outline_new=new,
        style_vector_text=task.get("style_vector_text", ""),
    )

    await tenancy.put(
        team_id=team_id,
        item={
            "pk": build_team_pk(team_id),
            "sk": f"OUTLINE_ADVICE#{generation_id}#v{task.get('version', 1)}",
            "advice": advice,
            "reviewed_at": _now(),
        },
    )


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
