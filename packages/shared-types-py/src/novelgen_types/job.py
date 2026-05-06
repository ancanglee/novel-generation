"""Job domain model: unified state machine for all long-running tasks (U1-F3=A)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class JobType(str, Enum):
    INGESTION = "ingestion"
    ANALYSIS = "analysis"
    OUTLINE = "outline"
    CHAPTER = "chapter"
    CRITIC = "critic"
    CONSISTENCY = "consistency"
    MODERATION = "moderation"
    EXPORT = "export"


_ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELED},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED},
    JobStatus.SUCCEEDED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELED: set(),
}


def is_valid_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
    return to_status in _ALLOWED_TRANSITIONS[from_status]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class Job(BaseModel):
    job_id: UUID
    team_id: UUID
    owner_user_id: UUID
    job_type: JobType
    subject_id: UUID
    status: JobStatus = JobStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    error_code: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    step_functions_execution_arn: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result_ref: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
