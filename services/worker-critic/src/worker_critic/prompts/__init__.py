"""Prompt templates for worker-critic."""

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def load(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")
