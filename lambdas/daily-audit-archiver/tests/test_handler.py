"""Unit tests for audit archiver using moto."""

from __future__ import annotations

import os

os.environ["AUDIT_TABLE"] = "novelgen_dev_audit"
os.environ["ARCHIVE_BUCKET"] = "novelgen-dev-audit-archive"
os.environ["ARCHIVE_AFTER_DAYS"] = "90"

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws_resources():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName="novelgen_dev_audit",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novelgen-dev-audit-archive")
        yield table, s3


def test_archive_empty_day_returns_zero(aws_resources):
    import importlib

    import handler as h

    importlib.reload(h)
    result = h.handler({"date": "2025-01-01"}, None)
    assert result["archived"] == 0


def test_archive_writes_gz_file(aws_resources):
    table, s3 = aws_resources
    table.put_item(
        Item={
            "pk": "DATE#20250101",
            "sk": "20250101T000001Z#abc",
            "action": "USER_CREATE",
            "actor_user_id": "u1",
        }
    )
    import importlib

    import handler as h

    importlib.reload(h)
    result = h.handler({"date": "2025-01-01"}, None)
    assert result["archived"] == 1
    assert result["s3_key"].endswith(".jsonl.gz")
    listed = s3.list_objects_v2(Bucket="novelgen-dev-audit-archive")
    assert listed["KeyCount"] == 1
