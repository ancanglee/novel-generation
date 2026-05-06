"""Prompt templates loaded from Markdown files."""

from __future__ import annotations

from pathlib import Path

_BASE = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    return (_BASE / f"{name}.md").read_text(encoding="utf-8")
