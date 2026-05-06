"""Business logic for novel ingestion: idempotency, dedup, Step Functions trigger."""

from __future__ import annotations

import json
import os
import unicodedata
from datetime import datetime, timezone
from uuid import UUID, uuid4

import aioboto3

from novelgen_storage import DynamoDBAdapter, S3Adapter, build_s3_prefix, build_team_pk
from novelgen_types.errors import ConflictError, NovelGenError
from novelgen_types.identity import Principal

from novelgen_api.deps import jobs_table, novels_bucket, tenancy_table

STATE_MACHINE_ARN = os.environ["INGESTION_STATE_MACHINE_ARN"]
REGION = os.environ.get("AWS_REGION", "us-east-1")


class TitleExistsError(NovelGenError):
    error_code = "CONFLICT_TITLE_EXISTS"
    http_status = 409

    def __init__(self, existing_novel_id: UUID) -> None:
        super().__init__("title already exists in team", existing_novel_id=str(existing_novel_id))
        self.existing_novel_id = existing_novel_id


def normalize_title(t: str) -> str:
    return unicodedata.normalize("NFKC", t).strip().lower()


async def idempotency_lookup(team_id: UUID, key: str) -> UUID | None:
    if not key:
        return None
    ddb = jobs_table()
    item = await ddb.get(
        team_id=team_id,
        pk=build_team_pk(team_id),
        sk=f"IDEMPOTENCY#{key}",
    )
    if not item:
        return None
    return UUID(item["novel_id"])


async def idempotency_store(team_id: UUID, key: str, novel_id: UUID) -> None:
    if not key:
        return
    ddb = jobs_table()
    ttl = int(datetime.now(tz=timezone.utc).timestamp()) + 86400
    await ddb.put(
        team_id=team_id,
        item={
            "pk": build_team_pk(team_id),
            "sk": f"IDEMPOTENCY#{key}",
            "novel_id": str(novel_id),
            "ttl": ttl,
        },
    )


async def find_existing_by_title(team_id: UUID, title: str) -> UUID | None:
    ddb = tenancy_table()
    target = normalize_title(title)
    items = await ddb.query_by_sk_prefix(team_id=team_id, sk_prefix="NOVEL#", limit=200)
    for row in items:
        if normalize_title(row.get("title", "")) == target:
            return UUID(row["novel_id"])
    return None


async def create_novel_row(
    principal: Principal,
    novel_id: UUID,
    title: str,
    source_type: str,
    source_url: str | None = None,
    original_format: str | None = None,
) -> None:
    ddb = tenancy_table()
    now = datetime.now(tz=timezone.utc).isoformat()
    await ddb.put(
        team_id=principal.team_id,
        item={
            "pk": build_team_pk(principal.team_id),
            "sk": f"NOVEL#{novel_id}",
            "novel_id": str(novel_id),
            "team_id": str(principal.team_id),
            "owner_user_id": str(principal.user_id),
            "title": title,
            "source_type": source_type,
            "source_url": source_url or "",
            "original_format": original_format or "",
            "status": "ingesting",
            "chapter_count": 0,
            "word_count": 0,
            "created_at": now,
            "updated_at": now,
        },
    )


async def create_job_row(principal: Principal, job_id: UUID, novel_id: UUID, payload: dict) -> None:
    ddb = jobs_table()
    now = datetime.now(tz=timezone.utc).isoformat()
    await ddb.put(
        team_id=principal.team_id,
        item={
            "pk": build_team_pk(principal.team_id),
            "sk": f"JOB#{job_id}",
            "job_id": str(job_id),
            "team_id": str(principal.team_id),
            "owner_user_id": str(principal.user_id),
            "job_type": "ingestion",
            "subject_id": str(novel_id),
            "status": "QUEUED",
            "progress": 0,
            "payload": payload,
            "created_at": now,
        },
    )


async def start_ingestion_execution(principal: Principal, job_id: UUID, payload: dict) -> str:
    session = aioboto3.Session()
    input_doc = {
        "team_id": str(principal.team_id),
        "team_pk": build_team_pk(principal.team_id),
        "job_sk": f"JOB#{job_id}",
        "job_id": str(job_id),
        "owner_user_id": str(principal.user_id),
        "payload": payload,
    }
    async with session.client("stepfunctions", region_name=REGION) as sfn:
        resp = await sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=str(job_id),
            input=json.dumps(input_doc),
        )
    return resp["executionArn"]


async def store_upload_content(
    principal: Principal, content: bytes, suffix: str
) -> str:
    bucket = novels_bucket()
    key = f"{build_s3_prefix(principal.team_id)}uploads/tmp/{uuid4()}.{suffix.lstrip('.')}"
    await bucket.put_object(principal.team_id, key, content)
    return key
