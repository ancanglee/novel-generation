"""Handler test using moto DynamoDB."""

from __future__ import annotations

import os

os.environ["TENANCY_TABLE"] = "novelgen_dev_tenancy"
os.environ["JOBS_TABLE"] = "novelgen_dev_jobs"

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def tables():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        for name in ("novelgen_dev_tenancy", "novelgen_dev_jobs"):
            t = ddb.create_table(
                TableName=name,
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
            t.wait_until_exists()
        tenancy = ddb.Table("novelgen_dev_tenancy")
        tenancy.put_item(
            Item={
                "pk": "TEAM#t1",
                "sk": "GEN#g1",
                "generation_id": "g1",
                "target_chapter_count": 50,
                "style_vector": {"tone": 70},
            }
        )
        yield ddb


def test_handler_writes_gen_context(tables):
    import importlib

    import handler as h

    importlib.reload(h)
    result = h.handler({"team_id": "t1", "generation_id": "g1"}, None)
    assert result["context"]["chapter_count"] == 50
    jobs = tables.Table("novelgen_dev_jobs")
    ctx = jobs.get_item(Key={"pk": "TEAM#t1", "sk": "GEN_CONTEXT#g1"}).get("Item")
    assert ctx is not None
    assert ctx["generation_id"] == "g1"
