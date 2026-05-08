"""Worker main loop: SQS consumer with asyncio Semaphore(5) + graceful shutdown.

Consumes ingestion-queue messages shaped as:
  {"kind": "upload|download|crawl", "taskToken": "...", "task": {<PipelineJob fields>}}

Reports back to Step Functions via SendTaskSuccess / SendTaskFailure.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from uuid import UUID

import aioboto3
from novelgen_browser_pool import BrowserPool
from novelgen_obs import get_logger, init_observability, set_request_id
from novelgen_storage import DynamoDBAdapter, S3Adapter

from worker_ingestion.pipeline import Pipeline, PipelineJob

log = get_logger("worker-ingestion")

QUEUE_URL = os.environ["INGESTION_QUEUE_URL"]
NOVELS_BUCKET = os.environ["NOVELS_BUCKET"]
TENANCY_TABLE = os.environ["TENANCY_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
REGION = os.environ.get("AWS_REGION", "us-west-2")
MAX_CONCURRENCY = int(os.environ.get("INGESTION_MAX_CONCURRENCY", "5"))


async def _run() -> None:
    init_observability("worker-ingestion", os.environ.get("ENV", "dev"))
    session = aioboto3.Session()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    pool = BrowserPool(JOBS_TABLE, region=REGION)
    s3 = S3Adapter(NOVELS_BUCKET, region=REGION)
    ddb = DynamoDBAdapter(TENANCY_TABLE, region=REGION)
    pipeline = Pipeline(novels_bucket=s3, tenancy_table=ddb, browser_pool=pool)

    async with session.client("sqs", region_name=REGION) as sqs, session.client(
        "stepfunctions", region_name=REGION
    ) as sfn:
        log.info("worker-ingestion started", extra={"queue": QUEUE_URL})
        while not stop_event.is_set():
            resp = await sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=min(MAX_CONCURRENCY, 10),
                WaitTimeSeconds=10,
                VisibilityTimeout=360,
            )
            messages = resp.get("Messages", [])
            if not messages:
                continue
            await asyncio.gather(
                *(_process_one(sqs, sfn, pipeline, sem, m) for m in messages)
            )
        log.info("worker-ingestion draining; in-flight tasks will complete within 30s")


async def _process_one(sqs, sfn, pipeline: Pipeline, sem: asyncio.Semaphore, msg: dict) -> None:
    receipt = msg["ReceiptHandle"]
    body = json.loads(msg["Body"])
    task_token = body.get("taskToken")
    task = body.get("task") or {}
    request_id = task.get("request_id") or msg.get("MessageId", "")
    set_request_id(request_id)

    async with sem:
        try:
            job = PipelineJob(
                job_id=str(task["job_id"]),
                team_id=UUID(task["team_id"]),
                novel_id=UUID(task["novel_id"]),
                owner_user_id=UUID(task["owner_user_id"]),
                kind=task["kind"],
                mime_type=task.get("mime_type"),
                upload_s3_key=task.get("upload_s3_key"),
                source_url=task.get("source_url"),
                title_hint=task.get("title_hint"),
            )
            outcome = await pipeline.run(job)
            if task_token:
                await sfn.send_task_success(
                    taskToken=task_token,
                    output=json.dumps(
                        {
                            "novel_id": str(outcome.novel_id),
                            "chapter_count": outcome.chapter_count,
                            "word_count": outcome.word_count,
                        }
                    ),
                )
            await sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt)
            log.info("job success", extra={"job_id": job.job_id})
        except Exception as e:
            log.exception("job failed", extra={"error": str(e)})
            if task_token:
                await sfn.send_task_failure(
                    taskToken=task_token,
                    error=type(e).__name__,
                    cause=str(e)[:1024],
                )
            # Let SQS redrive via DLQ; no explicit delete


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
