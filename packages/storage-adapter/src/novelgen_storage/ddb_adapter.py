"""DynamoDB adapter with enforced team-scope PK prefix (double guard at Adapter layer)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import aioboto3
from boto3.dynamodb.conditions import Key

from novelgen_storage.guards import build_team_pk, ensure_ddb_pk_in_team


class DynamoDBAdapter:
    """Generic DynamoDB table adapter. All operations require team_id and validate PK."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self._table_name = table_name
        self._region = region
        self._session = aioboto3.Session()

    async def put(self, team_id: UUID, item: dict[str, Any]) -> None:
        ensure_ddb_pk_in_team(item["pk"], team_id)
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            await table.put_item(Item=item)

    async def put_if_absent(self, team_id: UUID, item: dict[str, Any]) -> bool:
        """Idempotent put. Returns True if inserted, False if pk/sk already existed."""
        ensure_ddb_pk_in_team(item["pk"], team_id)
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            try:
                await table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
                )
                return True
            except ddb.meta.client.exceptions.ConditionalCheckFailedException:
                return False

    async def get(self, team_id: UUID, pk: str, sk: str) -> dict[str, Any] | None:
        ensure_ddb_pk_in_team(pk, team_id)
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            resp = await table.get_item(Key={"pk": pk, "sk": sk})
            return resp.get("Item")

    async def query_by_sk_prefix(
        self,
        team_id: UUID,
        sk_prefix: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        pk = build_team_pk(team_id)
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            resp = await table.query(
                KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with(sk_prefix),
                Limit=limit,
            )
            return resp.get("Items", [])

    async def update(
        self,
        team_id: UUID,
        pk: str,
        sk: str,
        update_expression: str,
        expression_values: dict[str, Any],
        expression_names: dict[str, str] | None = None,
        condition: str | None = None,
    ) -> dict[str, Any]:
        ensure_ddb_pk_in_team(pk, team_id)
        kwargs: dict[str, Any] = {
            "Key": {"pk": pk, "sk": sk},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_values,
            "ReturnValues": "ALL_NEW",
        }
        if expression_names:
            kwargs["ExpressionAttributeNames"] = expression_names
        if condition:
            kwargs["ConditionExpression"] = condition

        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            resp = await table.update_item(**kwargs)
            return resp.get("Attributes", {})

    async def delete(self, team_id: UUID, pk: str, sk: str) -> None:
        ensure_ddb_pk_in_team(pk, team_id)
        async with self._session.resource("dynamodb", region_name=self._region) as ddb:
            table = await ddb.Table(self._table_name)
            await table.delete_item(Key={"pk": pk, "sk": sk})

    async def transact_write(
        self,
        *,
        items: list[dict[str, Any]],
    ) -> None:
        """Run a DynamoDB TransactWriteItems call.

        `items` is a list of operation dicts as documented by boto3
        (each entry must contain exactly one of Put / Update / Delete / ConditionCheck
        whose TableName is already resolved). Caller is responsible for enforcing
        team-scope on any `pk` values in the payload; this adapter does NOT auto-guard
        transactional writes since they may cross SK namespaces (e.g. model_configs +
        audit_events).
        """
        async with self._session.client("dynamodb", region_name=self._region) as client:
            await client.transact_write_items(TransactItems=items)
