"""Tests for shared types: invariants, fact_key generation, job transitions."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from novelgen_types.fact import FactType, build_fact_key
from novelgen_types.identity import GlobalRole, Principal, TeamRole
from novelgen_types.job import JobStatus, is_valid_transition


def test_principal_is_frozen() -> None:
    p = Principal(
        user_id=uuid4(),
        team_id=uuid4(),
        email="a@b.com",
        global_role=GlobalRole.REGULAR,
        team_role=TeamRole.MEMBER,
        jwt_expiry=datetime.utcnow(),
    )
    with pytest.raises(Exception):
        p.team_id = uuid4()  # type: ignore[misc]


def test_admin_can_access_any_team() -> None:
    p = Principal(
        user_id=uuid4(),
        team_id=uuid4(),
        email="a@b.com",
        global_role=GlobalRole.ADMIN,
        team_role=TeamRole.OWNER,
        jwt_expiry=datetime.utcnow(),
    )
    assert p.can_access_team(uuid4()) is True


def test_regular_cannot_access_other_team() -> None:
    own_team = uuid4()
    other_team = uuid4()
    p = Principal(
        user_id=uuid4(),
        team_id=own_team,
        email="a@b.com",
        global_role=GlobalRole.REGULAR,
        team_role=TeamRole.MEMBER,
        jwt_expiry=datetime.utcnow(),
    )
    assert p.can_access_team(own_team) is True
    assert p.can_access_team(other_team) is False


@pytest.mark.parametrize(
    ("from_status", "to_status", "expected"),
    [
        (JobStatus.QUEUED, JobStatus.RUNNING, True),
        (JobStatus.QUEUED, JobStatus.CANCELED, True),
        (JobStatus.RUNNING, JobStatus.SUCCEEDED, True),
        (JobStatus.RUNNING, JobStatus.FAILED, True),
        (JobStatus.RUNNING, JobStatus.CANCELED, True),
        (JobStatus.SUCCEEDED, JobStatus.RUNNING, False),
        (JobStatus.FAILED, JobStatus.RUNNING, False),
        (JobStatus.CANCELED, JobStatus.RUNNING, False),
    ],
)
def test_job_transitions(from_status: JobStatus, to_status: JobStatus, expected: bool) -> None:
    assert is_valid_transition(from_status, to_status) is expected


def test_fact_key_character() -> None:
    key = build_fact_key(FactType.CHARACTER_SNAPSHOT, name="李云龙", chapter=5)
    assert key == "character:李云龙:chapter:5"


def test_fact_key_normalizes_whitespace() -> None:
    k1 = build_fact_key(FactType.MAP_PLACE, name="  长安 ")
    k2 = build_fact_key(FactType.MAP_PLACE, name="长安")
    assert k1 == k2


def test_fact_key_requires_params() -> None:
    with pytest.raises(ValueError):
        build_fact_key(FactType.CHARACTER_SNAPSHOT, name="x")  # missing chapter
