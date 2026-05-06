"""S3 adapter with enforced team-scope prefix."""

from __future__ import annotations

from typing import IO, Any
from uuid import UUID

import aioboto3

from novelgen_storage.guards import ensure_s3_key_in_team


class S3Adapter:
    """Async S3 client wrapper. All methods require explicit team_id and validate key prefix."""

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._region = region
        self._session = aioboto3.Session()

    async def put_object(
        self,
        team_id: UUID,
        key: str,
        body: bytes | IO[bytes],
        content_type: str = "application/octet-stream",
    ) -> str:
        ensure_s3_key_in_team(key, team_id)
        async with self._session.client("s3", region_name=self._region) as client:
            await client.put_object(
                Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
            )
        return f"s3://{self._bucket}/{key}"

    async def get_object(self, team_id: UUID, key: str) -> bytes:
        ensure_s3_key_in_team(key, team_id)
        async with self._session.client("s3", region_name=self._region) as client:
            resp = await client.get_object(Bucket=self._bucket, Key=key)
            async with resp["Body"] as stream:
                return await stream.read()

    async def delete_object(self, team_id: UUID, key: str) -> None:
        ensure_s3_key_in_team(key, team_id)
        async with self._session.client("s3", region_name=self._region) as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def delete_prefix(self, team_id: UUID, prefix: str) -> int:
        """Batch delete all objects under a prefix (used for Novel cascade delete)."""
        ensure_s3_key_in_team(prefix, team_id)
        deleted = 0
        async with self._session.client("s3", region_name=self._region) as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if not objs:
                    continue
                await client.delete_objects(
                    Bucket=self._bucket, Delete={"Objects": objs, "Quiet": True}
                )
                deleted += len(objs)
        return deleted

    async def presign_get(self, team_id: UUID, key: str, expires_seconds: int = 1800) -> str:
        ensure_s3_key_in_team(key, team_id)
        async with self._session.client("s3", region_name=self._region) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )

    async def presign_put(
        self,
        team_id: UUID,
        key: str,
        expires_seconds: int = 1800,
        content_type: str = "application/octet-stream",
    ) -> str:
        ensure_s3_key_in_team(key, team_id)
        async with self._session.client("s3", region_name=self._region) as client:
            return await client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires_seconds,
            )

    async def list_prefix(self, team_id: UUID, prefix: str) -> list[dict[str, Any]]:
        ensure_s3_key_in_team(prefix, team_id)
        results: list[dict[str, Any]] = []
        async with self._session.client("s3", region_name=self._region) as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                results.extend(page.get("Contents", []))
        return results
