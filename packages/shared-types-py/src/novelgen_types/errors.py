"""Unified domain exceptions for NovelGen (see business-rules R10)."""

from __future__ import annotations


class NovelGenError(Exception):
    """Base class for all domain exceptions. Each carries an error_code for API mapping."""

    error_code: str = "INTERNAL_UNEXPECTED"
    http_status: int = 500

    def __init__(self, message: str = "", **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class TeamScopeViolation(NovelGenError):
    """Raised when a storage operation crosses team boundaries."""

    error_code = "FORBIDDEN_SCOPE_VIOLATION"
    http_status = 403


class ForbiddenCrossTeamAccess(NovelGenError):
    """Raised when an API request carries a team_id not matching the Principal."""

    error_code = "FORBIDDEN_CROSS_TEAM_ACCESS"
    http_status = 403


class InvalidJobTransition(NovelGenError):
    error_code = "CONFLICT_JOB_TRANSITION"
    http_status = 409


class ConflictError(NovelGenError):
    error_code = "CONFLICT"
    http_status = 409


class UpstreamError(NovelGenError):
    error_code = "UPSTREAM_ERROR"
    http_status = 502


class FactKeyCollision(NovelGenError):
    error_code = "CONFLICT_FACT_KEY"
    http_status = 409


class AuthError(NovelGenError):
    error_code = "AUTH_FAILED"
    http_status = 401
