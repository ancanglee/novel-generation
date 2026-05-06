"""Test sampling bounds enforcement (no Bedrock calls)."""

from __future__ import annotations

from worker_analysis.agents.rough_read import _enforce_bounds


def test_bounds_enforces_min_size():
    selected = _enforce_bounds([5, 10], n_chapters=100)
    assert len(selected) >= 8


def test_bounds_caps_max_size():
    selected = _enforce_bounds(list(range(1, 30)), n_chapters=30)
    assert len(selected) <= 15


def test_bounds_always_includes_first_and_last():
    selected = _enforce_bounds([10, 20, 30], n_chapters=50)
    assert 1 in selected
    assert 50 in selected


def test_bounds_ignores_out_of_range():
    selected = _enforce_bounds([999], n_chapters=10)
    assert all(1 <= i <= 10 for i in selected)
