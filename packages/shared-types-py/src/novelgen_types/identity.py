"""Identity domain models: User / Team / Role / Principal."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GlobalRole(str, Enum):
    REGULAR = "regular_user"
    ADMIN = "admin"
    MODERATOR = "content_moderator"


class TeamRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TeamStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    email: EmailStr
    display_name: str
    team_id: UUID
    global_role: GlobalRole = GlobalRole.REGULAR
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime
    last_login_at: datetime | None = None


class Team(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: UUID
    name: str
    owner_user_id: UUID
    status: TeamStatus = TeamStatus.ACTIVE
    created_at: datetime


class Principal(BaseModel):
    """Immutable identity context resolved from Cognito JWT. Passed explicitly (U1-F5=C)."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    team_id: UUID
    email: EmailStr
    global_role: GlobalRole
    team_role: TeamRole
    jwt_expiry: datetime
    request_id: str = Field(default="", description="X-Request-Id for tracing")

    @property
    def is_admin(self) -> bool:
        return self.global_role == GlobalRole.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.global_role == GlobalRole.MODERATOR

    def can_access_team(self, team_id: UUID) -> bool:
        """Admin can access any team; others only their own."""
        return self.is_admin or self.team_id == team_id
