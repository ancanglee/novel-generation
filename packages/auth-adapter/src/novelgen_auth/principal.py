"""Principal construction from Cognito claims, exposed as FastAPI dependency."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from novelgen_types.errors import AuthError
from novelgen_types.identity import GlobalRole, Principal, TeamRole

from novelgen_auth.jwt_verifier import CognitoJwtVerifier


def _map_global_role(groups: list[str]) -> GlobalRole:
    if "admin" in groups:
        return GlobalRole.ADMIN
    if "content_moderator" in groups:
        return GlobalRole.MODERATOR
    return GlobalRole.REGULAR


def _parse_team_role(team_roles_claim: str | None, team_id: UUID) -> TeamRole:
    if not team_roles_claim:
        return TeamRole.MEMBER
    try:
        mapping = json.loads(team_roles_claim)
    except json.JSONDecodeError:
        return TeamRole.MEMBER
    value = mapping.get(str(team_id))
    if value == "owner":
        return TeamRole.OWNER
    if value == "moderator":
        return TeamRole.MODERATOR
    return TeamRole.MEMBER


def build_principal_from_claims(claims: dict[str, Any], request_id: str = "") -> Principal:
    """Convert Cognito claims dict to an immutable Principal."""
    try:
        user_id = UUID(claims["sub"])
        team_id = UUID(claims["custom:team_id"])
    except (KeyError, ValueError) as e:
        raise AuthError(f"missing or malformed identity claims: {e}") from e

    groups = claims.get("cognito:groups") or []
    if isinstance(groups, str):
        groups = [groups]

    return Principal(
        user_id=user_id,
        team_id=team_id,
        email=claims.get("email", ""),
        global_role=_map_global_role(groups),
        team_role=_parse_team_role(claims.get("custom:team_roles"), team_id),
        jwt_expiry=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
        request_id=request_id,
    )


# FastAPI wiring ------------------------------------------------------------

_verifier: CognitoJwtVerifier | None = None


def set_verifier(verifier: CognitoJwtVerifier) -> None:
    """Called during app startup to inject the verifier."""
    global _verifier
    _verifier = verifier


def get_verifier() -> CognitoJwtVerifier:
    if _verifier is None:
        raise RuntimeError("CognitoJwtVerifier not initialized; call set_verifier at startup")
    return _verifier


async def verify_principal(
    request: Request,
    authorization: str = Header(...),
    x_request_id: str = Header(default=""),
) -> Principal:
    """FastAPI dependency: verifies JWT and returns Principal."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"error": {"code": "AUTH_MISSING_BEARER"}})
    token = authorization.split(None, 1)[1]

    try:
        claims = get_verifier().verify(token)
        principal = build_principal_from_claims(claims, request_id=x_request_id)
    except AuthError as e:
        raise HTTPException(
            status_code=e.http_status,
            detail={"error": {"code": e.error_code, "message": str(e)}},
        ) from e

    # Stash on request.state so middleware (logging) can read it
    request.state.principal = principal
    return principal


# Re-export Depends(verify_principal) as the canonical injection point
PrincipalDep = Depends(verify_principal)
