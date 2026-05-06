"""Authorization decorators for FastAPI routes (R1.2, R3.4)."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable
from uuid import UUID

from fastapi import HTTPException

from novelgen_types.errors import ForbiddenCrossTeamAccess
from novelgen_types.identity import GlobalRole, Principal, TeamRole


def require_role(role: GlobalRole) -> Callable[..., Any]:
    """Require that the injected Principal has the given global_role."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = _extract_principal(kwargs)
            if principal.global_role != role and not principal.is_admin:
                raise HTTPException(
                    status_code=403,
                    detail={"error": {"code": "FORBIDDEN_ROLE", "required": role.value}},
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_team_role(team_role: TeamRole) -> Callable[..., Any]:
    """Require that Principal.team_role matches (admin bypasses)."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = _extract_principal(kwargs)
            if not principal.is_admin and principal.team_role != team_role:
                raise HTTPException(
                    status_code=403,
                    detail={"error": {"code": "FORBIDDEN_TEAM_ROLE"}},
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_team_access(team_id_param: str = "team_id") -> Callable[..., Any]:
    """Require that the route's team_id path/query parameter matches Principal.team_id.

    Admin bypasses. Raises 403 on mismatch.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = _extract_principal(kwargs)
            raw = kwargs.get(team_id_param)
            if raw is None:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "VALIDATION_TEAM_ID_MISSING",
                            "param": team_id_param,
                        }
                    },
                )
            try:
                requested_team = UUID(str(raw))
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail={"error": {"code": "VALIDATION_TEAM_ID_INVALID"}},
                ) from e

            if not principal.can_access_team(requested_team):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "code": ForbiddenCrossTeamAccess.error_code,
                            "message": "cross-team access denied",
                        }
                    },
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _extract_principal(kwargs: dict[str, Any]) -> Principal:
    for val in kwargs.values():
        if isinstance(val, Principal):
            return val
    raise HTTPException(
        status_code=500,
        detail={"error": {"code": "INTERNAL_NO_PRINCIPAL"}},
    )
