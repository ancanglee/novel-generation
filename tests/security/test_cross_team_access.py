"""US-NFR-03: multi-tenant isolation penetration test.

Runs the storage-adapter guard layer against synthetic team IDs to verify every known
cross-team vector is blocked. This test executes locally without AWS (no real DDB/S3),
exercising only the application-layer guards (D2=B). Integration-level tests against
a deployed stack live in tests/integration/.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from novelgen_storage.guards import (
    build_s3_prefix,
    build_team_pk,
    ensure_ddb_pk_in_team,
    ensure_s3_key_in_team,
)
from novelgen_types.errors import TeamScopeViolation


class TestCrossTeamS3Denial:
    """Validate every way to probe another team's S3 objects is rejected."""

    def test_attacker_guessing_owner_team_id(self):
        owner_team = uuid4()
        attacker_team = uuid4()
        # Attacker's principal (attacker_team) tries to read owner_team's S3 object.
        owner_key = f"{build_s3_prefix(owner_team)}novels/n1/raw.md"
        with pytest.raises(TeamScopeViolation):
            ensure_s3_key_in_team(owner_key, attacker_team)

    def test_attacker_without_prefix(self):
        attacker_team = uuid4()
        with pytest.raises(TeamScopeViolation):
            ensure_s3_key_in_team("novels/shared/raw.md", attacker_team)

    def test_attacker_directory_traversal(self):
        attacker_team = uuid4()
        with pytest.raises(TeamScopeViolation):
            ensure_s3_key_in_team(f"teams/../{build_s3_prefix(uuid4())}x", attacker_team)

    def test_attacker_empty_key(self):
        attacker_team = uuid4()
        with pytest.raises(TeamScopeViolation):
            ensure_s3_key_in_team("", attacker_team)


class TestCrossTeamDdbDenial:
    """Validate every way to probe another team's DynamoDB items is rejected."""

    def test_attacker_guessing_other_teams_pk(self):
        owner_team = uuid4()
        attacker_team = uuid4()
        with pytest.raises(TeamScopeViolation):
            ensure_ddb_pk_in_team(build_team_pk(owner_team), attacker_team)

    def test_attacker_empty_pk(self):
        with pytest.raises(TeamScopeViolation):
            ensure_ddb_pk_in_team("", uuid4())

    def test_attacker_wrong_prefix(self):
        with pytest.raises(TeamScopeViolation):
            ensure_ddb_pk_in_team("CONFIG", uuid4())


class TestHappyPath:
    """Matching team prefix is allowed."""

    def test_owner_own_s3_key_passes(self):
        team = uuid4()
        ensure_s3_key_in_team(f"{build_s3_prefix(team)}novels/n1/raw.md", team)

    def test_owner_own_ddb_pk_passes(self):
        team = uuid4()
        ensure_ddb_pk_in_team(build_team_pk(team), team)

    def test_extended_ddb_pk_passes(self):
        team = uuid4()
        ensure_ddb_pk_in_team(f"{build_team_pk(team)}#SUBNAMESPACE", team)


def test_exhaustive_pair_matrix():
    """For every (owner, attacker) pair, verify cross-team access is always blocked."""
    teams = [uuid4() for _ in range(5)]
    for i, owner in enumerate(teams):
        for j, attacker in enumerate(teams):
            if i == j:
                ensure_s3_key_in_team(f"{build_s3_prefix(owner)}x", attacker)
                ensure_ddb_pk_in_team(build_team_pk(owner), attacker)
            else:
                with pytest.raises(TeamScopeViolation):
                    ensure_s3_key_in_team(f"{build_s3_prefix(owner)}x", attacker)
                with pytest.raises(TeamScopeViolation):
                    ensure_ddb_pk_in_team(build_team_pk(owner), attacker)
