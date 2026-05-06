"""Tests for Principal construction from Cognito claims."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from novelgen_auth.principal import build_principal_from_claims
from novelgen_types.errors import AuthError
from novelgen_types.identity import GlobalRole, TeamRole


def _make_claims(**overrides: object) -> dict[str, object]:
    base = {
        "sub": str(uuid4()),
        "custom:team_id": str(uuid4()),
        "email": "alice@example.com",
        "exp": int((datetime.now(tz=UTC) + timedelta(hours=1)).timestamp()),
    }
    base.update(overrides)
    return base


def test_build_principal_regular_user() -> None:
    claims = _make_claims()
    p = build_principal_from_claims(claims, request_id="req-123")
    assert p.global_role == GlobalRole.REGULAR
    assert p.team_role == TeamRole.MEMBER
    assert p.request_id == "req-123"
    assert p.email == "alice@example.com"


def test_build_principal_admin_from_group() -> None:
    claims = _make_claims(**{"cognito:groups": ["admin"]})
    p = build_principal_from_claims(claims)
    assert p.global_role == GlobalRole.ADMIN


def test_build_principal_moderator() -> None:
    claims = _make_claims(**{"cognito:groups": ["content_moderator"]})
    p = build_principal_from_claims(claims)
    assert p.global_role == GlobalRole.MODERATOR


def test_team_role_from_claims() -> None:
    team_id = uuid4()
    claims = _make_claims(
        **{"custom:team_id": str(team_id), "custom:team_roles": f'{{"{team_id}":"owner"}}'}
    )
    p = build_principal_from_claims(claims)
    assert p.team_role == TeamRole.OWNER


def test_missing_team_id_raises() -> None:
    claims = {
        "sub": str(uuid4()),
        "email": "a@b.com",
        "exp": int(datetime.now(tz=UTC).timestamp()) + 3600,
    }
    with pytest.raises(AuthError):
        build_principal_from_claims(claims)


def test_malformed_uuid_raises() -> None:
    claims = _make_claims(sub="not-a-uuid")
    with pytest.raises(AuthError):
        build_principal_from_claims(claims)
