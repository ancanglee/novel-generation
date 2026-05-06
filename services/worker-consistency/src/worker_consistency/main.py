"""worker-consistency entrypoint.

Per message:
  1. Parse detail (generation_id, scan_to).
  2. advance_scan cursor — idempotent drop on duplicate.
  3. Load 10 chapters of text + memory facts + character snapshots.
  4. Run ConsistencyAgent → (report, conflicts).
  5. TransactWriteItems: CONSISTENCY# + N × CONFLICT# (batched <=20).
  6. Publish consistency.report_ready.
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

from .agent import (
    ConsistencyAgent,
    minimal_failure_report,
)
from .context import ConsistencyContext
from .event_publisher import ConsistencyEventPublisher
from .metrics import (
    emit_conflict,
    emit_duration_ms,
    emit_failure,
    emit_memory_unavailable,
    emit_total,
)
from .prompts import load as load_prompt
from .scan_cursor import advance_scan, get_last_scan_to
from .ssm_config import SsmConfigCache

log = logging.getLogger("worker_consistency")
logging.basicConfig(level=logging.INFO)

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_ENV = os.environ.get("NOVELGEN_ENV", "dev")
_QUEUE_URL = os.environ["CONSISTENCY_QUEUE_URL"]
_DDB_TABLE = os.environ["TENANCY_TABLE"]
_BUS = os.environ.get("EVENT_BUS", "novelgen-default-bus")
_CHAPTER_BUCKET = os.environ["CHAPTER_BUCKET"]

_TEMPLATE = load_prompt("consistency.md")
_MAX_CONFLICT_BATCH = 20


class WorkerConsistency:
    def __init__(self, memory_facade: Any | None = None) -> None:
        self._stop = asyncio.Event()
        self._session = aioboto3.Session()
        self._agent = ConsistencyAgent(region=_REGION)
        self._publisher = ConsistencyEventPublisher(bus_name=_BUS, region=_REGION)
        self._ssm = SsmConfigCache(
            prefix=f"/novelgen/{_ENV}/config", region=_REGION
        )
        # Lazy import so unit tests can inject None.
        if memory_facade is None:
            try:
                from novelgen_memory_facade import MemoryFacade

                self._memory = MemoryFacade(region=_REGION)
            except Exception:
                self._memory = None
        else:
            self._memory = memory_facade

    def request_stop(self) -> None:
        self._stop.set()

    async def _load_chapter(self, gid: UUID, idx: int) -> tuple[int, str]:
        key = f"generations/{gid}/chapters/{idx:05d}.md"
        async with self._session.client("s3", region_name=_REGION) as s3:
            try:
                obj = await s3.get_object(Bucket=_CHAPTER_BUCKET, Key=key)
                body = await obj["Body"].read()
                return idx, body.decode("utf-8")
            except Exception:
                return idx, ""

    async def _load_chapters(
        self, gid: UUID, scan_from: int, scan_to: int
    ) -> dict[int, str]:
        tasks = [self._load_chapter(gid, i) for i in range(scan_from, scan_to + 1)]
        results = await asyncio.gather(*tasks)
        return {idx: text for idx, text in results if text}

    async def _recall_facts(
        self, team_id: UUID, gid: UUID, scan_from: int, scan_to: int, top_k: int
    ) -> tuple[list[dict[str, Any]], bool]:
        if self._memory is None:
            return [], True
        try:
            query = f"chapters {scan_from}-{scan_to}"
            results = await self._memory.recall(
                team_id=team_id,
                novel_id=gid,
                query=query,
                top_k=top_k,
            )
            return list(results), False
        except Exception as exc:
            log.warning("memory_recall_failed err=%s", exc)
            return [], True

    async def _load_character_snapshots(
        self, team_id: UUID, gid: UUID, scan_to: int, main_characters: list[UUID]
    ) -> list[dict[str, Any]]:
        if self._memory is None or not main_characters:
            return []
        snaps: list[dict[str, Any]] = []
        for cid in main_characters:
            try:
                snap = await self._memory.get_character(
                    team_id=team_id,
                    novel_id=gid,
                    character_id=cid,
                    at_chapter=scan_to,
                )
                if snap:
                    snaps.append({"character_id": str(cid), **snap})
            except Exception:
                continue
        return snaps

    async def _load_main_characters(
        self, team_id: UUID, gid: UUID
    ) -> list[UUID]:
        """Read from Generation record or Outline meta. Fallback: empty."""
        pk = f"TEAM#{team_id}"
        sk = f"GEN#{gid}"
        async with self._session.client("dynamodb", region_name=_REGION) as ddb:
            resp = await ddb.get_item(
                TableName=_DDB_TABLE,
                Key={"pk": {"S": pk}, "sk": {"S": sk}},
                ProjectionExpression="main_character_ids",
            )
        raw = resp.get("Item", {}).get("main_character_ids", {}).get("SS", [])
        out: list[UUID] = []
        for s in raw:
            try:
                out.append(UUID(s))
            except ValueError:
                continue
        return out

    async def _persist(self, report, conflicts) -> None:
        """Write report + conflicts in batches (TransactWrite 25-item limit)."""
        async with self._session.client("dynamodb", region_name=_REGION) as ddb:
            # Always write the report first (its own transaction).
            await ddb.put_item(
                TableName=_DDB_TABLE,
                Item={
                    "pk": {"S": f"TEAM#{report.team_id}"},
                    "sk": {
                        "S": f"CONSISTENCY#{report.generation_id}#{report.scan_to:05d}"
                    },
                    "report": {"S": report.model_dump_json()},
                    "scan_from": {"N": str(report.scan_from)},
                    "scan_to": {"N": str(report.scan_to)},
                    "conflict_count": {"N": str(len(report.conflict_ids))},
                    "memory_unavailable": {"BOOL": report.memory_unavailable},
                    "minimal": {"BOOL": report.minimal},
                    "created_at": {"S": report.created_at.isoformat()},
                },
            )
            # Then write conflicts in batches of 20.
            for i in range(0, len(conflicts), _MAX_CONFLICT_BATCH):
                batch = conflicts[i : i + _MAX_CONFLICT_BATCH]
                transact_items = [
                    {
                        "Put": {
                            "TableName": _DDB_TABLE,
                            "Item": {
                                "pk": {"S": f"TEAM#{c.team_id}"},
                                "sk": {
                                    "S": f"CONFLICT#{c.generation_id}#{c.conflict_id}"
                                },
                                "conflict": {"S": c.model_dump_json()},
                                "scan_to": {"N": str(c.scan_to)},
                                "type": {"S": c.type.value},
                                "rewrite_attempts": {"N": "0"},
                                "frozen": {"BOOL": False},
                                "user_action": {"S": c.user_action.value},
                                "created_at": {"S": c.created_at.isoformat()},
                                "updated_at": {"S": c.updated_at.isoformat()},
                            },
                        }
                    }
                    for c in batch
                ]
                await ddb.transact_write_items(TransactItems=transact_items)

    async def _handle(self, body: dict[str, Any]) -> None:
        detail = body.get("detail", body)
        generation_id = UUID(detail["generation_id"])
        team_id = UUID(detail["team_id"])
        scan_to = int(detail.get("scan_to") or detail.get("chapter_idx"))

        # Cursor first — if already advanced, no-op.
        cursor = await advance_scan(
            table=_DDB_TABLE,
            team_id=team_id,
            generation_id=generation_id,
            scan_to=scan_to,
            region=_REGION,
        )
        if not cursor.advanced:
            log.info(
                "skip_duplicate_scan gid=%s scan_to=%s previous=%s",
                generation_id,
                scan_to,
                cursor.previous_scan_to,
            )
            return

        await get_last_scan_to(
            table=_DDB_TABLE,
            team_id=team_id,
            generation_id=generation_id,
            region=_REGION,
        )
        # previous is now scan_to (we just advanced); derive scan_from from the event payload.
        scan_from = max(1, scan_to - 9)  # 10-chapter window; overlap tolerated

        top_k = await self._ssm.get_int("consistency-top-k", 30)
        emit_total(_ENV)
        t0 = time.monotonic()

        chapters, facts_and_flag, main_chars = await asyncio.gather(
            self._load_chapters(generation_id, scan_from, scan_to),
            self._recall_facts(team_id, generation_id, scan_from, scan_to, top_k),
            self._load_main_characters(team_id, generation_id),
        )
        facts, memory_unavailable = facts_and_flag
        snapshots = await self._load_character_snapshots(
            team_id, generation_id, scan_to, main_chars
        )

        if memory_unavailable:
            emit_memory_unavailable(_ENV)

        ctx = ConsistencyContext(
            generation_id=generation_id,
            team_id=team_id,
            scan_from=scan_from,
            scan_to=scan_to,
            chapters_text=chapters,
            memory_facts=facts,
            character_snapshots=snapshots,
            memory_unavailable=memory_unavailable,
            env=_ENV,
            request_id=detail.get("event_id", f"{generation_id}:{scan_to}"),
        )

        try:
            report, conflicts = await self._agent.run(template=_TEMPLATE, ctx=ctx)
        except Exception as exc:
            emit_failure(_ENV, type(exc).__name__)
            report = minimal_failure_report(ctx)
            conflicts = []

        await self._persist(report, conflicts)

        for c in conflicts:
            emit_conflict(_ENV, c.type.value)

        await self._publisher.publish_report_ready(
            generation_id=report.generation_id,
            team_id=report.team_id,
            scan_from=report.scan_from,
            scan_to=report.scan_to,
            conflict_count=len(conflicts),
            memory_unavailable=report.memory_unavailable,
        )
        emit_duration_ms((time.monotonic() - t0) * 1000.0, _ENV)
        log.info(
            "consistency_done gid=%s window=%s-%s conflicts=%s mem_unavail=%s",
            generation_id,
            scan_from,
            scan_to,
            len(conflicts),
            memory_unavailable,
        )

    async def _poll(self) -> None:
        async with self._session.client("sqs", region_name=_REGION) as sqs:
            while not self._stop.is_set():
                resp = await sqs.receive_message(
                    QueueUrl=_QUEUE_URL,
                    MaxNumberOfMessages=3,
                    WaitTimeSeconds=10,
                    VisibilityTimeout=360,
                )
                messages = resp.get("Messages", [])
                if not messages:
                    continue
                for msg in messages:
                    try:
                        body = json.loads(msg["Body"])
                    except Exception as exc:
                        log.error("bad_message_body err=%s", exc)
                        continue
                    try:
                        await self._handle(body)
                        await sqs.delete_message(
                            QueueUrl=_QUEUE_URL,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                    except Exception as exc:
                        log.exception("handle_failed err=%s", exc)

    async def run(self) -> None:
        await self._poll()


async def _amain() -> None:
    worker = WorkerConsistency()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_stop)
    await worker.run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
