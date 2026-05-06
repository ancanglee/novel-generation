"""System configuration models: ModelConfig / ConcurrencyConfig / AlertRule."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ModelStage(str, Enum):
    CLASSIFICATION = "classification"
    CHARACTER = "character"
    MAP = "map"
    STYLE = "style"
    OUTLINE = "outline"
    CHAPTER = "chapter"
    SELF_CRITIQUE = "self_critique"
    CRITIC = "critic"
    CONSISTENCY = "consistency"


class ModelEntry(BaseModel):
    model_id: str
    fallback: str | None = None


class ModelConfig(BaseModel):
    config_id: UUID
    version: int = Field(ge=1)
    mapping: dict[ModelStage, ModelEntry]
    updated_by_user_id: UUID
    updated_at: datetime


DEFAULT_MODEL_MAPPING: dict[ModelStage, ModelEntry] = {
    ModelStage.CLASSIFICATION: ModelEntry(
        model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
        fallback="anthropic.claude-sonnet-4-6-v1:0",
    ),
    ModelStage.CHARACTER: ModelEntry(model_id="anthropic.claude-sonnet-4-6-v1:0"),
    ModelStage.MAP: ModelEntry(model_id="anthropic.claude-sonnet-4-6-v1:0"),
    ModelStage.STYLE: ModelEntry(model_id="anthropic.claude-sonnet-4-7-v1:0"),
    ModelStage.OUTLINE: ModelEntry(model_id="anthropic.claude-opus-4-7-v1:0"),
    ModelStage.CHAPTER: ModelEntry(
        model_id="anthropic.claude-sonnet-4-7-v1:0",
        fallback="anthropic.claude-sonnet-4-6-v1:0",
    ),
    ModelStage.SELF_CRITIQUE: ModelEntry(model_id="anthropic.claude-sonnet-4-6-v1:0"),
    ModelStage.CRITIC: ModelEntry(model_id="anthropic.claude-opus-4-7-v1:0"),
    ModelStage.CONSISTENCY: ModelEntry(model_id="anthropic.claude-sonnet-4-6-v1:0"),
}


class ConcurrencyConfig(BaseModel):
    config_id: UUID
    deep_read_max: int = Field(default=50, ge=1, le=200)
    dynamic_enabled: bool = True
    updated_by_user_id: UUID
    updated_at: datetime


class AlertMetric(str, Enum):
    BEDROCK_ERROR_RATE = "BEDROCK_ERROR_RATE"
    JOB_TIMEOUT = "JOB_TIMEOUT"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    MEMORY_WRITE_FAILURE = "MEMORY_WRITE_FAILURE"
    CROSS_TEAM_DENIED = "CROSS_TEAM_DENIED"
    JOB_TOKEN_SPIKE = "JOB_TOKEN_SPIKE"
    TEAM_HOURLY_TOKEN = "TEAM_HOURLY_TOKEN"


class AlertRule(BaseModel):
    rule_id: UUID
    metric: AlertMetric
    threshold: float
    window_minutes: int = Field(default=5, ge=1)
    sns_topic_arn: str
    enabled: bool = True
