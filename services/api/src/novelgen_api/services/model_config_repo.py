"""ModelConfig repository with optimistic locking.

Writes combine the business row + AuditEvent via DDB TransactWriteItems.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from novelgen_storage import DynamoDBAdapter

_REGION = os.environ.get("AWS_REGION", "us-east-1")

CONFIG_PK = "CONFIG"


class OptimisticLockError(Exception):
    """Raised when an admin PUT collides with a concurrent update."""


@dataclass
class ModelConfigRecord:
    stage: str
    primary: dict[str, Any]
    fallback: dict[str, Any] | None
    version: int
    updated_by: str
    updated_at: str


class ModelConfigRepo:
    def __init__(
        self,
        tenancy: DynamoDBAdapter,
        audit_table_name: str,
        tenancy_table_name: str,
    ) -> None:
        self._tenancy = tenancy
        self._audit_table = audit_table_name
        self._tenancy_table = tenancy_table_name

    async def list_all(self) -> list[ModelConfigRecord]:
        items = await self._tenancy.query_by_sk_prefix(
            team_id=_zero_uuid(),
            sk_prefix="MODEL_CONFIG#",
            limit=50,
        )
        return [self._to_record(it) for it in items]

    async def get(self, stage: str) -> ModelConfigRecord | None:
        item = await self._tenancy.get(
            team_id=_zero_uuid(),
            pk=CONFIG_PK,
            sk=f"MODEL_CONFIG#{stage}",
        )
        return self._to_record(item) if item else None

    async def put_with_audit(
        self,
        *,
        stage: str,
        primary: dict[str, Any],
        fallback: dict[str, Any] | None,
        expected_version: int,
        audit_item: dict[str, Any],
        updated_by: str,
        updated_at: str,
    ) -> ModelConfigRecord:
        new_version = expected_version + 1
        item = {
            "pk": {"S": CONFIG_PK},
            "sk": {"S": f"MODEL_CONFIG#{stage}"},
            "stage": {"S": stage},
            "primary": {"S": json.dumps(primary)},
            "version": {"N": str(new_version)},
            "updated_by": {"S": updated_by},
            "updated_at": {"S": updated_at},
        }
        if fallback is not None:
            item["fallback"] = {"S": json.dumps(fallback)}

        condition = (
            "attribute_not_exists(version) OR version = :expected"
            if expected_version == 0
            else "version = :expected"
        )

        try:
            await self._tenancy.transact_write(
                items=[
                    {
                        "Put": {
                            "TableName": self._tenancy_table,
                            "Item": item,
                            "ConditionExpression": condition,
                            "ExpressionAttributeValues": {
                                ":expected": {"N": str(expected_version)},
                            },
                        }
                    },
                    audit_item,
                ]
            )
        except Exception as exc:
            msg = str(exc)
            if "ConditionalCheckFailed" in msg or "TransactionCanceled" in msg:
                raise OptimisticLockError(stage) from exc
            raise

        return ModelConfigRecord(
            stage=stage,
            primary=primary,
            fallback=fallback,
            version=new_version,
            updated_by=updated_by,
            updated_at=updated_at,
        )

    @staticmethod
    def _to_record(item: dict[str, Any]) -> ModelConfigRecord:
        primary_raw = item.get("primary") or {}
        if isinstance(primary_raw, str):
            try:
                primary = json.loads(primary_raw)
            except Exception:
                primary = {}
        elif isinstance(primary_raw, dict):
            primary = primary_raw
        else:
            primary = {}
        fallback_raw = item.get("fallback")
        if isinstance(fallback_raw, str):
            try:
                fallback = json.loads(fallback_raw)
            except Exception:
                fallback = None
        elif isinstance(fallback_raw, dict):
            fallback = fallback_raw
        else:
            fallback = None
        return ModelConfigRecord(
            stage=str(item.get("stage", "")),
            primary=primary,
            fallback=fallback,
            version=int(item.get("version", 0)),
            updated_by=str(item.get("updated_by", "")),
            updated_at=str(item.get("updated_at", "")),
        )


def _zero_uuid() -> UUID:
    """CONFIG rows are non-team-scoped; use a sentinel UUID to satisfy adapter guards."""
    return UUID("00000000-0000-0000-0000-000000000000")
