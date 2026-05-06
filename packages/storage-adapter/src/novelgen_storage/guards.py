"""Team-scope guards. Raise TeamScopeViolation if key/PK doesn't start with team prefix."""

from __future__ import annotations

from uuid import UUID

from novelgen_types.errors import TeamScopeViolation


def build_s3_prefix(team_id: UUID) -> str:
    return f"teams/{team_id}/"


def build_team_pk(team_id: UUID) -> str:
    return f"TEAM#{team_id}"


def ensure_s3_key_in_team(key: str, team_id: UUID) -> None:
    prefix = build_s3_prefix(team_id)
    if not key.startswith(prefix):
        raise TeamScopeViolation(
            f"S3 key does not start with team prefix",
            key=key,
            expected_prefix=prefix,
        )


def ensure_ddb_pk_in_team(pk: str, team_id: UUID) -> None:
    expected = build_team_pk(team_id)
    if not pk.startswith(expected):
        raise TeamScopeViolation(
            "DynamoDB PK does not start with team prefix",
            pk=pk,
            expected_prefix=expected,
        )
