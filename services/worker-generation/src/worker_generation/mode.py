"""Generation mode enum (F1=A)."""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    CLEAN_ROOM = "clean_room"       # 同风格新世界 (全新仿写)
    CONTINUATION = "continuation"   # 续写原作


def prompt_name_for(mode: Mode) -> str:
    """Map mode to its system prompt file name (without .md)."""
    return mode.value
