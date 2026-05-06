"""Daily audit archiver Lambda.

Reads audit events from `novelgen_*_audit` older than 90 days, writes them to S3
as newline-delimited JSON (Glacier tier via bucket lifecycle), and does NOT delete
from DynamoDB (audit table is RETAIN-forever per NFR-8.1; archive is redundant copy
for Athena queries).
"""

from __future__ import annotations

import gzip
import io
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

AUDIT_TABLE = os.environ["AUDIT_TABLE"]
ARCHIVE_BUCKET = os.environ["ARCHIVE_BUCKET"]
ENV = os.environ.get("ENV", "dev")
ARCHIVE_AFTER_DAYS = int(os.environ.get("ARCHIVE_AFTER_DAYS", "90"))

_ddb = boto3.resource("dynamodb")
_s3 = boto3.client("s3")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    target_date = _resolve_target_date(event)
    date_pk = f"DATE#{target_date.strftime('%Y%m%d')}"
    table = _ddb.Table(AUDIT_TABLE)

    buffer = io.BytesIO()
    writer = gzip.GzipFile(fileobj=buffer, mode="wb")
    count = 0

    resp = table.query(KeyConditionExpression=Key("pk").eq(date_pk))
    for item in resp.get("Items", []):
        writer.write((json.dumps(item, default=str) + "\n").encode("utf-8"))
        count += 1
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("pk").eq(date_pk),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        for item in resp.get("Items", []):
            writer.write((json.dumps(item, default=str) + "\n").encode("utf-8"))
            count += 1
    writer.close()

    if count == 0:
        return {"date": target_date.isoformat(), "archived": 0}

    key = f"audit/{target_date.strftime('%Y/%m/%d')}/events.jsonl.gz"
    buffer.seek(0)
    _s3.put_object(
        Bucket=ARCHIVE_BUCKET,
        Key=key,
        Body=buffer.read(),
        ContentType="application/gzip",
        ContentEncoding="gzip",
    )

    return {"date": target_date.isoformat(), "archived": count, "s3_key": key}


def _resolve_target_date(event: dict[str, Any]):
    override = event.get("date") if event else None
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return (datetime.now(tz=UTC) - timedelta(days=ARCHIVE_AFTER_DAYS)).date()
