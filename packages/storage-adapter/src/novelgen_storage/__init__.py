"""Storage adapters with enforced multi-tenant guards."""

from novelgen_storage.ddb_adapter import DynamoDBAdapter
from novelgen_storage.guards import (
    build_s3_prefix,
    build_team_pk,
    ensure_ddb_pk_in_team,
    ensure_s3_key_in_team,
)
from novelgen_storage.s3_adapter import S3Adapter

__all__ = [
    "DynamoDBAdapter",
    "S3Adapter",
    "build_s3_prefix",
    "build_team_pk",
    "ensure_ddb_pk_in_team",
    "ensure_s3_key_in_team",
]
