"""GEN_SCAN# cursor: serialize Consistency scans per generation.

Guarantees that only scans with strictly increasing scan_to are accepted —
later messages with smaller scan_to are silently dropped (idempotent).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import aioboto3


@dataclass(frozen=True)
class CursorAdvanceResult:
    advanced: bool
    previous_scan_to: int


async def advance_scan(
    *,
    table: str,
    team_id: UUID,
    generation_id: UUID,
    scan_to: int,
    region: str = "us-east-1",
) -> CursorAdvanceResult:
    """Try to advance the scan cursor to scan_to.

    Returns advanced=False if a concurrent scan already advanced past scan_to.
    """
    pk = f"TEAM#{team_id}"
    sk = f"GEN_SCAN#{generation_id}"
    session = aioboto3.Session()
    async with session.client("dynamodb", region_name=region) as ddb:
        try:
            await ddb.update_item(
                TableName=table,
                Key={"pk": {"S": pk}, "sk": {"S": sk}},
                UpdateExpression="SET last_scan_to = :new",
                ConditionExpression=(
                    "attribute_not_exists(last_scan_to) OR last_scan_to < :new"
                ),
                ExpressionAttributeValues={
                    ":new": {"N": str(scan_to)},
                },
                ReturnValues="UPDATED_OLD",
            )
            return CursorAdvanceResult(advanced=True, previous_scan_to=0)
        except ddb.exceptions.ConditionalCheckFailedException:
            # Fetch current value so caller can decide whether to no-op
            resp = await ddb.get_item(
                TableName=table,
                Key={"pk": {"S": pk}, "sk": {"S": sk}},
                ProjectionExpression="last_scan_to",
            )
            prev = int(
                resp.get("Item", {}).get("last_scan_to", {}).get("N", "0")
            )
            return CursorAdvanceResult(advanced=False, previous_scan_to=prev)


async def get_last_scan_to(
    *,
    table: str,
    team_id: UUID,
    generation_id: UUID,
    region: str = "us-east-1",
) -> int:
    pk = f"TEAM#{team_id}"
    sk = f"GEN_SCAN#{generation_id}"
    session = aioboto3.Session()
    async with session.client("dynamodb", region_name=region) as ddb:
        resp = await ddb.get_item(
            TableName=table,
            Key={"pk": {"S": pk}, "sk": {"S": sk}},
            ProjectionExpression="last_scan_to",
        )
    return int(resp.get("Item", {}).get("last_scan_to", {}).get("N", "0"))
