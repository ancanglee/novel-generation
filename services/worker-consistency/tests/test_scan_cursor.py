"""Tests for scan_cursor using moto-mocked DynamoDB."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from worker_consistency.scan_cursor import advance_scan, get_last_scan_to

_TABLE = "novelgen_tenancy_test"


def _setup_table() -> None:
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName=_TABLE,
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def mock_ddb():
    with mock_aws():
        _setup_table()
        yield


def test_first_advance_accepted(mock_ddb) -> None:
    team_id = uuid4()
    gid = uuid4()
    result = asyncio.run(
        advance_scan(
            table=_TABLE,
            team_id=team_id,
            generation_id=gid,
            scan_to=10,
            region="us-east-1",
        )
    )
    assert result.advanced is True
    last = asyncio.run(
        get_last_scan_to(
            table=_TABLE,
            team_id=team_id,
            generation_id=gid,
            region="us-east-1",
        )
    )
    assert last == 10


def test_out_of_order_advance_rejected(mock_ddb) -> None:
    team_id = uuid4()
    gid = uuid4()
    asyncio.run(
        advance_scan(
            table=_TABLE,
            team_id=team_id,
            generation_id=gid,
            scan_to=20,
            region="us-east-1",
        )
    )
    # older scan_to: should be rejected
    result = asyncio.run(
        advance_scan(
            table=_TABLE,
            team_id=team_id,
            generation_id=gid,
            scan_to=10,
            region="us-east-1",
        )
    )
    assert result.advanced is False
    assert result.previous_scan_to == 20


def test_monotonic_advance(mock_ddb) -> None:
    team_id = uuid4()
    gid = uuid4()
    for s in [10, 20, 30]:
        r = asyncio.run(
            advance_scan(
                table=_TABLE,
                team_id=team_id,
                generation_id=gid,
                scan_to=s,
                region="us-east-1",
            )
        )
        assert r.advanced is True
    last = asyncio.run(
        get_last_scan_to(
            table=_TABLE,
            team_id=team_id,
            generation_id=gid,
            region="us-east-1",
        )
    )
    assert last == 30
