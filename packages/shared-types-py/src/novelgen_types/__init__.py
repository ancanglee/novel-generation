"""Shared Pydantic domain models for NovelGen platform."""

from novelgen_types.audit import AuditAction, AuditEvent
from novelgen_types.config import (
    AlertMetric,
    AlertRule,
    ConcurrencyConfig,
    ModelConfig,
    ModelEntry,
    ModelStage,
)
from novelgen_types.critique import (
    ConflictItem,
    ConflictType,
    ConsistencyReport,
    CritiqueReport,
    CrossChapterConcern,
    Issue,
    IssueDimension,
    Severity,
    UserAction,
)
from novelgen_types.errors import (
    ConflictError,
    ForbiddenCrossTeamAccess,
    InvalidJobTransition,
    NovelGenError,
    TeamScopeViolation,
    UpstreamError,
)
from novelgen_types.fact import Fact, FactType, build_fact_key
from novelgen_types.identity import GlobalRole, Principal, Team, TeamRole, User, UserStatus
from novelgen_types.job import Job, JobStatus, JobType
from novelgen_types.novel import Novel, NovelSourceType, NovelStatus

__all__ = [
    "AlertMetric",
    "AlertRule",
    "AuditAction",
    "AuditEvent",
    "ConcurrencyConfig",
    "ConflictError",
    "ConflictItem",
    "ConflictType",
    "ConsistencyReport",
    "CritiqueReport",
    "CrossChapterConcern",
    "Fact",
    "FactType",
    "ForbiddenCrossTeamAccess",
    "GlobalRole",
    "InvalidJobTransition",
    "Issue",
    "IssueDimension",
    "Job",
    "JobStatus",
    "JobType",
    "ModelConfig",
    "ModelEntry",
    "ModelStage",
    "Novel",
    "NovelGenError",
    "NovelSourceType",
    "NovelStatus",
    "Principal",
    "Severity",
    "Team",
    "TeamRole",
    "TeamScopeViolation",
    "UpstreamError",
    "User",
    "UserAction",
    "UserStatus",
    "build_fact_key",
]
