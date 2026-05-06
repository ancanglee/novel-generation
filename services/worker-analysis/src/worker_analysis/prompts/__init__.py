"""Prompt templates loaded from Markdown files next to this module."""

from __future__ import annotations

from pathlib import Path

_BASE = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    path = _BASE / f"{name}.md"
    return path.read_text(encoding="utf-8")


__all__ = ["load_prompt"]
