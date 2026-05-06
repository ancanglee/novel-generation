"""Unit tests for team-scope guards. These are the core of NFR-4 defense-in-depth."""

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


def test_s3_prefix_format() -> None:
    team = uuid4()
    assert build_s3_prefix(team) == f"teams/{team}/"


def test_ddb_pk_format() -> None:
    team = uuid4()
    assert build_team_pk(team) == f"TEAM#{team}"


def test_s3_key_in_team_passes_on_matching_prefix() -> None:
    team = uuid4()
    ensure_s3_key_in_team(f"teams/{team}/novels/n1/raw.md", team)  # should not raise


def test_s3_key_in_team_rejects_cross_team() -> None:
    owner = uuid4()
    attacker = uuid4()
    with pytest.raises(TeamScopeViolation):
        ensure_s3_key_in_team(f"teams/{attacker}/novels/n1/raw.md", owner)


def test_s3_key_rejects_missing_prefix() -> None:
    with pytest.raises(TeamScopeViolation):
        ensure_s3_key_in_team("novels/n1/raw.md", uuid4())


def test_ddb_pk_in_team_passes() -> None:
    team = uuid4()
    ensure_ddb_pk_in_team(f"TEAM#{team}", team)
    ensure_ddb_pk_in_team(f"TEAM#{team}#EXTRA", team)  # extended PKs still valid


def test_ddb_pk_rejects_cross_team() -> None:
    owner = uuid4()
    attacker = uuid4()
    with pytest.raises(TeamScopeViolation):
        ensure_ddb_pk_in_team(f"TEAM#{attacker}", owner)


def test_ddb_pk_rejects_missing_prefix() -> None:
    with pytest.raises(TeamScopeViolation):
        ensure_ddb_pk_in_team("USER#foo", uuid4())
