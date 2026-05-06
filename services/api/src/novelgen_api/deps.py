"""Dependency wiring: adapters and config shared across routers."""

from __future__ import annotations

import os
from functools import lru_cache

from novelgen_storage import DynamoDBAdapter, S3Adapter


@lru_cache(maxsize=1)
def novels_bucket() -> S3Adapter:
    return S3Adapter(
        bucket=os.environ["NOVELS_BUCKET"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
    )


@lru_cache(maxsize=1)
def tenancy_table() -> DynamoDBAdapter:
    return DynamoDBAdapter(
        table_name=os.environ["TENANCY_TABLE"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
    )


@lru_cache(maxsize=1)
def jobs_table() -> DynamoDBAdapter:
    return DynamoDBAdapter(
        table_name=os.environ["JOBS_TABLE"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
    )
