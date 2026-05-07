"""Smoke test: module imports cleanly."""

from __future__ import annotations


def test_import_main() -> None:
    from worker_moderation import main as mod

    assert callable(mod.main)
    assert hasattr(mod, "WorkerModeration")
