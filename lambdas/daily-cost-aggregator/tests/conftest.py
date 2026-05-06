"""每次加载本 lambda 的 handler 时，显式把本目录放到 sys.path 首位并清 handler 缓存。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HANDLER_DIR = Path(__file__).resolve().parent.parent

os.environ.setdefault("AUDIT_TABLE", "novelgen_audit_test")
os.environ.setdefault("TENANCY_TABLE", "novelgen_tenancy_test")
os.environ.setdefault("JOBS_TABLE", "novelgen_jobs_test")
os.environ.setdefault("NOVELS_BUCKET", "novelgen-novels-test")
os.environ.setdefault("AUDIT_ARCHIVE_BUCKET", "novelgen-audit-archive-test")
os.environ.setdefault("CONFIG_TABLE", "novelgen_config_test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(autouse=True)
def _reset_handler_import(monkeypatch):
    """强制每个 lambda 测试以本目录的 handler.py 为 `handler` 模块。"""
    monkeypatch.syspath_prepend(str(_HANDLER_DIR))
    sys.modules.pop("handler", None)
    yield
    sys.modules.pop("handler", None)
