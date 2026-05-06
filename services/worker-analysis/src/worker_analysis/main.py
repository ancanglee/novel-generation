"""Worker main loop: SQS consumer + Supervisor + Step Functions callback.

Runs a single novel analysis per SQS message. Supervisor dispatches to sub-agents.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any
from uuid import UUID

import aioboto3
from novelgen_obs import get_logger, set_request_id
from novelgen_storage import DynamoDBAdapter, S3Adapter, build_s3_prefix

from worker_analysis.agentcore_registration import AgentCoreRegistrar
from worker_analysis.agents import (
    analyze_style,
    classify_tags,
    extract_chapter_all,
    extract_characters_global,
    extract_map_global,
    rewrite_character_profile,
    sample_chapters,
    write_memory,
)
from worker_analysis.checkpoint import CheckpointStore
from worker_analysis.memory.agentcore_memory import AgentCoreMemoryClient
from worker_analysis.memory.facade_impl import MemoryFacadeImpl
from worker_analysis.memory.neptune_client import NeptuneSignedClient
from worker_analysis.memory.opensearch_client import OpenSearchVectorClient
from worker_analysis.supervisor import Supervisor, SupervisorContext

log = get_logger("worker-analysis")

QUEUE_URL = os.environ["ANALYSIS_QUEUE_URL"]
NOVELS_BUCKET = os.environ["NOVELS_BUCKET"]
TENANCY_TABLE = os.environ["TENANCY_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
NEPTUNE_ENDPOINT = os.environ.get("NEPTUNE_ENDPOINT", "")
OPENSEARCH_ENDPOINT = os.environ.get("OPENSEARCH_ENDPOINT", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")
ENV = os.environ.get("ENV", "dev")


async def _run() -> None:
    session = aioboto3.Session()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    jobs_table = DynamoDBAdapter(JOBS_TABLE, region=REGION)
    registrar = AgentCoreRegistrar(jobs_table, agent_id=f"novelgen-understanding-{ENV}", env=ENV)
    await registrar.register_if_needed()

    s3 = S3Adapter(NOVELS_BUCKET, region=REGION)
    facade = MemoryFacadeImpl(
        agentcore=AgentCoreMemoryClient(region=REGION),
        neptune=NeptuneSignedClient(NEPTUNE_ENDPOINT, region=REGION) if NEPTUNE_ENDPOINT else None,  # type: ignore[arg-type]
        opensearch=OpenSearchVectorClient(OPENSEARCH_ENDPOINT, region=REGION) if OPENSEARCH_ENDPOINT else None,  # type: ignore[arg-type]
    )
    checkpoint = CheckpointStore(jobs_table)

    dispatcher = _build_dispatcher(s3, facade)
    supervisor = Supervisor(dispatcher=dispatcher, checkpoint=checkpoint, region=REGION)

    async with session.client("sqs", region_name=REGION) as sqs, session.client(
        "stepfunctions", region_name=REGION
    ) as sfn:
        log.info("worker-analysis started", extra={"queue": QUEUE_URL})
        while not stop_event.is_set():
            resp = await sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,
                VisibilityTimeout=1200,
            )
            messages = resp.get("Messages", [])
            for msg in messages:
                await _handle_message(sqs, sfn, supervisor, msg)


async def _handle_message(sqs, sfn, supervisor: Supervisor, msg: dict) -> None:
    receipt = msg["ReceiptHandle"]
    body = json.loads(msg["Body"])
    task_token = body.get("taskToken")
    task = body.get("task") or {}
    set_request_id(msg.get("MessageId", ""))

    try:
        ctx = SupervisorContext(
            team_id=UUID(task["team_id"]),
            job_id=UUID(task["job_id"]),
            novel_id=UUID(task["novel_id"]),
            chapter_count=int(task.get("chapter_count", 0)),
        )
        result = await supervisor.run(ctx)

        if task_token:
            await sfn.send_task_success(taskToken=task_token, output=json.dumps(result, default=str))
        await sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)
        log.info("analysis job success", extra={"job_id": str(ctx.job_id)})
    except Exception as e:
        log.exception("analysis job failed")
        if task_token:
            await sfn.send_task_failure(taskToken=task_token, error=type(e).__name__, cause=str(e)[:1024])


def _build_dispatcher(s3: S3Adapter, facade: MemoryFacadeImpl):
    """Return an async callable (tool, args, ctx) -> result used by Supervisor."""

    async def dispatch(tool: str, args: dict[str, Any], ctx: SupervisorContext) -> dict[str, Any]:
        if tool == "sample_chapters":
            titles = args.get("chapter_titles") or []
            return {"selected": await sample_chapters(titles, args.get("total_words", 0), args.get("goal", ""))}
        if tool == "classify_tags":
            text = await _load_samples_text(s3, ctx, args.get("chapter_indices", []))
            return {"tags": await classify_tags(text)}
        if tool == "extract_characters_global":
            text = await _load_samples_text(s3, ctx, args.get("chapter_indices", []))
            return {"characters": await extract_characters_global(text, args.get("novel_tags"))}
        if tool == "extract_map_global":
            text = await _load_samples_text(s3, ctx, args.get("chapter_indices", []))
            return await extract_map_global(text)
        if tool == "analyze_style":
            text = await _load_samples_text(s3, ctx, args.get("chapter_indices", []))
            return await analyze_style(text)
        if tool == "extract_chapter_all":
            idx = int(args["chapter_idx"])
            text = await _load_chapter_text(s3, ctx, idx)
            return await extract_chapter_all(
                chapter_idx=idx,
                chapter_title=args.get("chapter_title", f"第 {idx} 章"),
                chapter_text=text,
                known_characters=args.get("known_characters"),
                known_places=args.get("known_places"),
                novel_tags=args.get("novel_tags"),
            )
        if tool == "rewrite_character_profile":
            return await rewrite_character_profile(
                character_id=args["character_id"],
                display_name=args.get("display_name", ""),
                history_summary=args.get("history_summary", ""),
                reason=args.get("reason", ""),
            )
        if tool == "write_memory":
            return await write_memory(
                facade,
                ctx.team_id,
                ctx.novel_id,
                facts=args.get("facts") or [],
                nodes=args.get("nodes") or [],
                edges=args.get("edges") or [],
            )
        return {"error": f"unknown tool: {tool}"}

    return dispatch


async def _load_chapter_text(s3: S3Adapter, ctx: SupervisorContext, idx: int) -> str:
    key = f"{build_s3_prefix(ctx.team_id)}novels/{ctx.novel_id}/chapters/{idx:05d}.md"
    data = await s3.get_object(ctx.team_id, key)
    return data.decode("utf-8", errors="replace")


async def _load_samples_text(
    s3: S3Adapter, ctx: SupervisorContext, indices: list[int]
) -> str:
    chunks: list[str] = []
    for idx in indices:
        try:
            chunks.append(await _load_chapter_text(s3, ctx, idx))
        except Exception as e:
            log.warning("chapter load failed", extra={"idx": idx, "error": str(e)})
    return "\n\n---\n\n".join(chunks)


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
