"""U7 Admin API integration smoke tests.

Covers:
- require_admin_role: 403 for non-admin; 200 for admin
- Monitoring summary: minute-bucket cache hit
- Model config optimistic lock: 409 on stale version
- Audit viewer side-channel log is produced
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Request
from novelgen_types.identity import GlobalRole, Principal, TeamRole


@pytest.fixture()
def admin_principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        team_id=uuid4(),
        email="admin@example.com",
        global_role=GlobalRole.ADMIN,
        team_role=TeamRole.OWNER,
        jwt_expiry=datetime.utcnow() + timedelta(hours=1),
        request_id="test-req",
    )


@pytest.fixture()
def regular_principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        team_id=uuid4(),
        email="user@example.com",
        global_role=GlobalRole.REGULAR,
        team_role=TeamRole.MEMBER,
        jwt_expiry=datetime.utcnow() + timedelta(hours=1),
        request_id="test-req",
    )


def test_require_admin_role_403(regular_principal: Principal) -> None:
    from fastapi import HTTPException
    from novelgen_api.routers.admin._deps import require_admin_role

    req = _fake_request()
    with pytest.raises(HTTPException) as exc:
        require_admin_role(req, regular_principal)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "FORBIDDEN"


def test_require_admin_role_200(admin_principal: Principal) -> None:
    from novelgen_api.routers.admin._deps import require_admin_role

    req = _fake_request()
    out = require_admin_role(req, admin_principal)
    assert out is admin_principal


def test_monitoring_cache_bucket() -> None:
    from novelgen_api.routers.admin._cache import (
        cache_clear,
        cache_get,
        cache_set,
        minute_bucket,
    )

    cache_clear()
    t0 = datetime(2026, 4, 30, 10, 0, 15, tzinfo=UTC)
    t1 = datetime(2026, 4, 30, 10, 0, 45, tzinfo=UTC)  # same minute
    t2 = datetime(2026, 4, 30, 11, 0, 0, tzinfo=UTC)

    cache_set(t0, t2, {"value": 42})
    assert cache_get(t1, t2) == {"value": 42}  # same bucket hit

    t2b = datetime(2026, 4, 30, 11, 1, 0, tzinfo=UTC)
    assert cache_get(t1, t2b) is None  # different bucket, miss

    assert minute_bucket(t0) == minute_bucket(t1)


def test_audit_put_item_shape(admin_principal: Principal) -> None:
    from novelgen_api.routers.admin._deps import make_audit_put_item

    item = make_audit_put_item(
        table_name="audit_events",
        actor=admin_principal,
        action="admin.model_config.update",
        resource_type="model_config",
        resource_id="chapter",
        details={"before": None, "after": {"stage": "chapter"}},
    )
    put = item["Put"]
    assert put["TableName"] == "audit_events"
    assert put["Item"]["action"]["S"] == "admin.model_config.update"
    assert put["Item"]["actor_user_id"]["S"] == str(admin_principal.user_id)
    assert (
        put["ConditionExpression"]
        == "attribute_not_exists(pk) AND attribute_not_exists(sk)"
    )


def test_paginator_slice() -> None:
    from novelgen_api.routers.admin._deps import Paginator

    items = [{"i": i} for i in range(130)]
    p1 = Paginator.slice(items, page_size=50, cursor=None)
    assert len(p1.items) == 50 and p1.next_cursor == "50"
    p2 = Paginator.slice(items, page_size=50, cursor=p1.next_cursor)
    assert len(p2.items) == 50 and p2.next_cursor == "100"
    p3 = Paginator.slice(items, page_size=50, cursor=p2.next_cursor)
    assert len(p3.items) == 30 and p3.next_cursor is None


@pytest.mark.asyncio
async def test_model_config_optimistic_lock() -> None:
    from novelgen_api.services.model_config_repo import (
        ModelConfigRepo,
        OptimisticLockError,
    )

    repo = ModelConfigRepo(
        tenancy=AsyncMock(),
        audit_table_name="audit",
        tenancy_table_name="tenancy",
    )
    # Simulate DDB raising a ConditionalCheckFailed on transact_write.
    class _Err(Exception):
        pass

    repo._tenancy.transact_write = AsyncMock(  # type: ignore[attr-defined]
        side_effect=_Err("TransactionCanceledException: ConditionalCheckFailed")
    )
    audit_put = {"Put": {"TableName": "audit", "Item": {}}}
    with pytest.raises(OptimisticLockError):
        await repo.put_with_audit(
            stage="chapter",
            primary={"model_id": "claude-sonnet-4-7", "max_output_tokens": 4096, "temperature": 0.7},
            fallback=None,
            expected_version=3,
            audit_item=audit_put,
            updated_by="admin-id",
            updated_at="2026-04-30T00:00:00Z",
        )


def _fake_request() -> Request:
    scope = {
        "type": "http",
        "headers": [],
        "method": "GET",
        "path": "/admin/users",
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
    }
    req = Request(scope)
    req.state.request_id = "req-test"
    return req
