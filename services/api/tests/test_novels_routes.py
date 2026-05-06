"""API route tests with mocked principals + services."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

os.environ.setdefault("NOVELS_BUCKET", "bucket")
os.environ.setdefault("TENANCY_TABLE", "novelgen_dev_tenancy")
os.environ.setdefault("JOBS_TABLE", "novelgen_dev_jobs")
os.environ.setdefault("INGESTION_STATE_MACHINE_ARN", "arn:aws:states:us-east-1:123:stateMachine:foo")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_test")
os.environ.setdefault("COGNITO_APP_CLIENT_ID", "test-client")

import pytest
from fastapi.testclient import TestClient

from novelgen_auth.principal import verify_principal
from novelgen_types.identity import GlobalRole, Principal, TeamRole


def _fake_principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        team_id=uuid4(),
        email="alice@example.com",
        global_role=GlobalRole.REGULAR,
        team_role=TeamRole.MEMBER,
        jwt_expiry=datetime.now(tz=timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def client():
    from novelgen_api.main import create_app

    app = create_app()
    # Bypass Cognito for tests
    app.dependency_overrides[verify_principal] = lambda: _fake_principal()
    return TestClient(app)


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_novels_empty(client):
    with patch(
        "novelgen_api.routers.novels.tenancy_table",
        return_value=AsyncMock(query_by_sk_prefix=AsyncMock(return_value=[])),
    ):
        resp = client.get("/api/v1/novels")
        assert resp.status_code == 200
        assert resp.json() == []


def test_upload_rejects_unsupported_mime(client):
    files = {"file": ("foo.bin", b"binary", "application/x-binary")}
    resp = client.post("/api/v1/novels/upload", files=files, params={"title": "t"})
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "VALIDATION_UNSUPPORTED_FORMAT"
