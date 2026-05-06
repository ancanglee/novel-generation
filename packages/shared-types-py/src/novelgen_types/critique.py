"""U5 Critic & Consistency domain models.

Covers:
- CritiqueReport / Issue / CrossChapterConcern (Critic Layer-2, Opus 4.7)
- ConsistencyReport / ConflictItem (Consistency scan, Sonnet 4.6)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class IssueDimension(str, Enum):
    PLOT = "plot"
    CHARACTER = "character"
    STYLE = "style"
    PACING = "pacing"
    LOGIC = "logic"


class ConflictType(str, Enum):
    CHARACTER_STATE = "character_state"
    PLOT_HOLE = "plot_hole"
    TIMELINE = "timeline"
    LOCATION = "location"
    RELATION = "relation"
    WORLDBUILDING = "worldbuilding"


class UserAction(str, Enum):
    OPEN = "open"
    IGNORED = "ignored"
    REWRITE_REQUESTED = "rewrite_requested"


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Severity
    dimension: IssueDimension
    message: str = Field(min_length=1, max_length=1000)
    evidence_excerpt: str | None = Field(default=None, max_length=500)


class CrossChapterConcern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter_refs: list[int] = Field(min_length=1, max_length=10)
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("chapter_refs")
    @classmethod
    def _refs_positive(cls, v: list[int]) -> list[int]:
        if any(i < 1 for i in v):
            raise ValueError("chapter_refs must be positive")
        return v


class CritiqueReport(BaseModel):
    """Layer-2 critic report produced by Opus 4.7."""

    model_config = ConfigDict(extra="forbid")
    generation_id: UUID
    team_id: UUID
    chapter_idx: int = Field(ge=1)
    model: str = Field(default="claude-opus-4-7")
    score: int = Field(ge=0, le=100)
    layer1_confirmed: list[str] = Field(default_factory=list)
    layer1_overridden: list[str] = Field(default_factory=list)
    layer2_issues: list[Issue] = Field(default_factory=list)
    cross_chapter_concerns: list[CrossChapterConcern] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)
    minimal: bool = Field(
        default=False,
        description="True when upstream (Opus) failed and we emitted a placeholder.",
    )
    created_at: datetime


class ConflictItem(BaseModel):
    """A single cross-chapter conflict detected by Consistency scan."""

    model_config = ConfigDict(extra="forbid")
    conflict_id: UUID
    generation_id: UUID
    team_id: UUID
    scan_to: int = Field(ge=1, description="Chapter idx where this conflict was detected.")
    type: ConflictType
    chapter_refs: list[int] = Field(min_length=1, max_length=10)
    summary: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    rewrite_attempts: int = Field(default=0, ge=0)
    frozen: bool = False
    user_action: UserAction = UserAction.OPEN
    created_at: datetime
    updated_at: datetime

    @field_validator("chapter_refs")
    @classmethod
    def _refs_positive(cls, v: list[int]) -> list[int]:
        if any(i < 1 for i in v):
            raise ValueError("chapter_refs must be positive")
        return v


class ConsistencyReport(BaseModel):
    """Aggregated consistency scan report (every N chapters)."""

    model_config = ConfigDict(extra="forbid")
    generation_id: UUID
    team_id: UUID
    scan_from: int = Field(ge=1)
    scan_to: int = Field(ge=1)
    model: str = Field(default="claude-sonnet-4-6")
    conflict_ids: list[UUID] = Field(default_factory=list)
    memory_unavailable: bool = False
    characters_scanned: list[UUID] = Field(default_factory=list)
    minimal: bool = False
    created_at: datetime

    @field_validator("scan_to")
    @classmethod
    def _scan_to_ge_from(cls, v: int, info) -> int:
        scan_from = info.data.get("scan_from")
        if scan_from is not None and v < scan_from:
            raise ValueError("scan_to must be >= scan_from")
        return v


__all__ = [
    "ConflictItem",
    "ConflictType",
    "ConsistencyReport",
    "CritiqueReport",
    "CrossChapterConcern",
    "Issue",
    "IssueDimension",
    "Severity",
    "UserAction",
]
