"""Unit test for cost aggregator date-resolution logic."""

from __future__ import annotations

import os
from datetime import date, timedelta

os.environ["CONFIG_TABLE"] = "novelgen_dev_config"


def test_resolve_target_date_default_is_yesterday():
    import handler as h

    target = h._resolve_target_date({})
    assert target == (date.today() - timedelta(days=1))


def test_resolve_target_date_with_override():
    import handler as h

    target = h._resolve_target_date({"date": "2026-01-15"})
    assert target == date(2026, 1, 15)
