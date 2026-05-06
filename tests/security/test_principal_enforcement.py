"""Principal-layer authorization checks: covers US-01-04."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from novelgen_types.identity import GlobalRole, Principal, TeamRole


def _make_principal(team_id, role=GlobalRole.REGULAR):
    return Principal(
        user_id=uuid4(),
        team_id=team_id,
        email="alice@example.com",
        global_role=role,
        team_role=TeamRole.MEMBER,
        jwt_expiry=datetime.now(tz=UTC) + timedelta(hours=1),
    )


def test_regular_user_denied_cross_team():
    own = uuid4()
    other = uuid4()
    p = _make_principal(own)
    assert p.can_access_team(own) is True
    assert p.can_access_team(other) is False


def test_admin_allowed_cross_team():
    p = _make_principal(uuid4(), role=GlobalRole.ADMIN)
    for _ in range(20):
        assert p.can_access_team(uuid4()) is True
