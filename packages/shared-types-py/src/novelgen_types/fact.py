"""Fact model for MemoryFacade: business-key idempotent writes (U1-F6=B)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FactType(str, Enum):
    CHARACTER_SNAPSHOT = "CHARACTER_SNAPSHOT"
    MAP_PLACE = "MAP_PLACE"
    MAP_EDGE = "MAP_EDGE"
    EVENT = "EVENT"
    STYLE_VECTOR = "STYLE_VECTOR"
    RULE = "RULE"


def _normalize(value: str) -> str:
    """Normalize names for idempotent fact_key generation."""
    cleaned = unicodedata.normalize("NFKC", value).strip().lower()
    return re.sub(r"\s+", "-", cleaned)


def build_fact_key(
    fact_type: FactType,
    *,
    name: str | None = None,
    chapter: int | None = None,
    edge_type: str | None = None,
    place_a: str | None = None,
    place_b: str | None = None,
    seq: int | None = None,
    novel_id: UUID | None = None,
    rule_text: str | None = None,
) -> str:
    """Produce a deterministic business key per R5.1 rules."""
    match fact_type:
        case FactType.CHARACTER_SNAPSHOT:
            if name is None or chapter is None:
                raise ValueError("CHARACTER_SNAPSHOT requires name and chapter")
            return f"character:{_normalize(name)}:chapter:{chapter}"
        case FactType.MAP_PLACE:
            if name is None:
                raise ValueError("MAP_PLACE requires name")
            return f"place:{_normalize(name)}"
        case FactType.MAP_EDGE:
            if not (place_a and place_b and edge_type):
                raise ValueError("MAP_EDGE requires place_a, place_b, edge_type")
            return f"edge:{_normalize(place_a)}:{_normalize(edge_type)}:{_normalize(place_b)}"
        case FactType.EVENT:
            if chapter is None or seq is None:
                raise ValueError("EVENT requires chapter and seq")
            return f"event:{chapter}:{seq}"
        case FactType.STYLE_VECTOR:
            if novel_id is None:
                raise ValueError("STYLE_VECTOR requires novel_id")
            return f"style:{novel_id}"
        case FactType.RULE:
            if rule_text is None:
                raise ValueError("RULE requires rule_text")
            return f"rule:{_normalize(rule_text)}"


class Fact(BaseModel):
    fact_key: str
    team_id: UUID
    novel_id: UUID
    fact_type: FactType
    content: dict[str, Any]
    source_chapter: int | None = None
    embedding: list[float] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
