"""worker-critic entrypoint: consume critic-queue, emit CritiqueReport.

Flow per message:
  1. Parse SQS body → detail (generation_id, team_id, chapter_idx).
  2. Load chapter text (S3), Layer-1 critique (DDB), Outline.items (S3), style_vector.
  3. Build CriticContext → CriticAgent.run() → CritiqueReport.
     On 3-attempt exhaustion → minimal_failure_report (N3=A, business continues).
  4. PutItem CRITIQUE# in DDB tenancy table.
  5. PutEvents critic.report_ready.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from typing import Any
from uuid import UUID

import aioboto3

from .agent import CriticAgent, CriticAgentError, minimal_failure_report
from .context import CriticContext, pick_recent_summaries
from .event_publisher import CriticEventPublisher
from .metrics import emit_duration_ms, emit_failure, emit_score_bucket, emit_total
from .prompts import load as load_prompt
from .ssm_config import SsmConfigCache

log = logging.getLogger("worker_critic")
logging.basicConfig(level=logging.INFO)

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_ENV = os.environ.get("NOVELGEN_ENV", "dev")
_QUEUE_URL = os.environ["CRITIC_QUEUE_URL"]
_DDB_TABLE = os.environ["TENANCY_TABLE"]
_BUS = os.environ.get("EVENT_BUS", "novelgen-default-bus")
_CHAPTER_BUCKET = os.environ["CHAPTER_BUCKET"]
_OUTLINE_BUCKET = os.environ["OUTLINE_BUCKET"]

_TEMPLATE = load_prompt("critic_layer2.md")


class WorkerCritic:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._session = aioboto3.Session()
        self._agent = CriticAgent(region=_REGION)
        self._publisher = CriticEventPublisher(bus_name=_BUS, region=_REGION)
        self._ssm = SsmConfigCache(
            prefix=f"/novelgen/{_ENV}/config", region=_REGION
        )

    def request_stop(self) -> None:
        self._stop.set()

    async def _load_chapter_text(self, gid: UUID, idx: int) -> str:
        key = f"generations/{gid}/chapters/{idx:05d}.md"
        async with self._session.client("s3", region_name=_REGION) as s3:
            obj = await s3.get_object(Bucket=_CHAPTER_BUCKET, Key=key)
            body = await obj["Body"].read()
        return body.decode("utf-8")

    async def _load_outline_items(self, gid: UUID) -> list[dict[str, Any]]:
        key = f"generations/{gid}/outline.json"
        async with self._session.client("s3", region_name=_REGION) as s3:
            try:
                obj = await s3.get_object(Bucket=_OUTLINE_BUCKET, Key=key)
            except Exception:
                return []
            body = await obj["Body"].read()
        data = json.loads(body)
        return data.get("items", [])

    async def _load_layer1_critique(
        self, team_id: UUID, gid: UUID, idx: int
    ) -> dict[str, Any]:
        pk = f"TEAM#{team_id}"
        sk = f"GEN_CHAPTER#{gid}#{idx:05d}"
        async with self._session.client("dynamodb", region_name=_REGION) as ddb:
            resp = await ddb.get_item(
                TableName=_DDB_TABLE,
                Key={"pk": {"S": pk}, "sk": {"S": sk}},
                ProjectionExpression="self_critique, style_vector",
            )
        item = resp.get("Item", {})
        critique_raw = item.get("self_critique", {}).get("S", "{}")
        style_raw = item.get("style_vector", {}).get("S", "{}")
        try:
            critique = json.loads(critique_raw)
        except Exception:
            critique = {}
        try:
            style = json.loads(style_raw)
        except Exception:
            style = {}
        return {"critique": critique, "style_vector": style}

    async def _write_report(self, report) -> None:
        pk = f"TEAM#{report.team_id}"
        sk = f"CRITIQUE#{report.generation_id}#{report.chapter_idx:05d}"
        async with self._session.client("dynamodb", region_name=_REGION) as ddb:
            await ddb.put_item(
                TableName=_DDB_TABLE,
                Item={
                    "pk": {"S": pk},
                    "sk": {"S": sk},
                    "report": {"S": report.model_dump_json()},
                    "score": {"N": str(report.score)},
                    "minimal": {"BOOL": report.minimal},
                    "chapter_idx": {"N": str(report.chapter_idx)},
                    "created_at": {"S": report.created_at.isoformat()},
                },
            )

    async def _handle(self, body: dict[str, Any]) -> None:
        detail = body.get("detail", body)
        generation_id = UUID(detail["generation_id"])
        team_id = UUID(detail["team_id"])
        chapter_idx = int(detail["chapter_idx"])
        request_id = detail.get("event_id") or f"{generation_id}:{chapter_idx}:critic"

        summary_count = await self._ssm.get_int(
            "critic-layer2-recent-summary-count", 5
        )

        t0 = time.monotonic()
        emit_total(_ENV)

        try:
            chapter_text, outline_items, layer1_and_style = await asyncio.gather(
                self._load_chapter_text(generation_id, chapter_idx),
                self._load_outline_items(generation_id),
                self._load_layer1_critique(team_id, generation_id, chapter_idx),
            )
            recent = pick_recent_summaries(outline_items, chapter_idx, summary_count)
            ctx = CriticContext(
                generation_id=generation_id,
                team_id=team_id,
                chapter_idx=chapter_idx,
                chapter_text=chapter_text,
                layer1_critique=layer1_and_style["critique"],
                recent_summaries=recent,
                style_vector=layer1_and_style["style_vector"],
                env=_ENV,
                request_id=request_id,
            )
            report = await self._agent.run(template=_TEMPLATE, ctx=ctx)
        except (CriticAgentError, Exception) as exc:  # noqa: BLE001
            log.warning("critic_failed gid=%s idx=%s err=%s", generation_id, chapter_idx, exc)
            emit_failure(_ENV, type(exc).__name__)
            ctx = CriticContext(
                generation_id=generation_id,
                team_id=team_id,
                chapter_idx=chapter_idx,
                chapter_text="",
                layer1_critique={},
                recent_summaries=[],
                style_vector={},
                env=_ENV,
                request_id=request_id,
            )
            report = minimal_failure_report(ctx, str(exc))

        await self._write_report(report)
        await self._publisher.publish_report_ready(
            generation_id=report.generation_id,
            team_id=report.team_id,
            chapter_idx=report.chapter_idx,
            score=report.score,
            minimal=report.minimal,
        )
        emit_score_bucket(report.score, _ENV)
        emit_duration_ms((time.monotonic() - t0) * 1000.0, _ENV)
        log.info(
            "critic_done gid=%s idx=%s score=%s minimal=%s",
            generation_id,
            chapter_idx,
            report.score,
            report.minimal,
        )

    async def _poll(self) -> None:
        async with self._session.client("sqs", region_name=_REGION) as sqs:
            while not self._stop.is_set():
                resp = await sqs.receive_message(
                    QueueUrl=_QUEUE_URL,
                    MaxNumberOfMessages=5,
                    WaitTimeSeconds=10,
                    VisibilityTimeout=180,
                )
                messages = resp.get("Messages", [])
                if not messages:
                    continue
                for msg in messages:
                    try:
                        body = json.loads(msg["Body"])
                    except Exception as exc:  # noqa: BLE001
                        log.error("bad_message_body err=%s", exc)
                        continue
                    try:
                        await self._handle(body)
                        await sqs.delete_message(
                            QueueUrl=_QUEUE_URL,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.exception("handle_failed err=%s", exc)

    async def run(self) -> None:
        await self._poll()


async def _amain() -> None:
    worker = WorkerCritic()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_stop)
    await worker.run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
