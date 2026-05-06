"""Novel skeleton (U2 will extend)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class NovelSourceType(str, Enum):
    UPLOAD = "upload"
    PUBLIC_DOMAIN = "public_domain"
    CRAWL = "crawl"


class NovelStatus(str, Enum):
    INGESTING = "ingesting"
    INGESTED = "ingested"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"


class Novel(BaseModel):
    novel_id: UUID
    team_id: UUID
    owner_user_id: UUID
    title: str
    source_type: NovelSourceType
    status: NovelStatus = NovelStatus.INGESTING
    chapter_count: int = Field(default=0, ge=0)
    word_count: int = Field(default=0, ge=0)
    created_at: datetime
