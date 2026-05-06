"""Audit domain model: admin management operations only (U1-F4=A)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditAction(str, Enum):
    USER_CREATE = "USER_CREATE"
    USER_DISABLE = "USER_DISABLE"
    TEAM_CREATE = "TEAM_CREATE"
    TEAM_DISABLE = "TEAM_DISABLE"
    TEAM_DELETE = "TEAM_DELETE"
    MEMBER_ADD = "MEMBER_ADD"
    MEMBER_REMOVE = "MEMBER_REMOVE"
    MODEL_CONFIG_UPDATE = "MODEL_CONFIG_UPDATE"
    CONCURRENCY_UPDATE = "CONCURRENCY_UPDATE"
    SCHEMA_UPSERT = "SCHEMA_UPSERT"
    TAG_MERGE = "TAG_MERGE"
    ALERT_UPSERT = "ALERT_UPSERT"


class AuditEvent(BaseModel):
    """Append-only audit record. Stored in novelgen_audit with IAM write lock."""

    model_config = ConfigDict(frozen=True)

    audit_id: UUID
    timestamp: datetime
    actor_user_id: UUID
    actor_team_id: UUID
    action: AuditAction
    target_type: str
    target_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: str = Field(default="")
