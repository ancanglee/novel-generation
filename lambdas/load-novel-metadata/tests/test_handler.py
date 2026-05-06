"""Tests using moto DynamoDB."""

from __future__ import annotations

import os

os.environ["TENANCY_TABLE"] = "novelgen_dev_tenancy"

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def table_with_data():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
            TableName="novelgen_dev_tenancy",
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
        pk = "TEAM#team-a"
        novel_id = "novel-1"
        table.put_item(Item={"pk": pk, "sk": f"NOVEL#{novel_id}", "title": "测试", "word_count": 12345})
        for i in range(1, 6):
            table.put_item(
                Item={
                    "pk": pk,
                    "sk": f"CHAPTER#{novel_id}#{i:05d}",
                    "chapter_idx": i,
                    "title": f"第 {i} 章",
                    "word_count": 2000,
                }
            )
        yield table


def test_handler_returns_chapter_metadata(table_with_data):
    import importlib

    import handler as h

    importlib.reload(h)
    result = h.handler({"team_id": "team-a", "novel_id": "novel-1"}, None)
    assert result["chapter_count"] == 5
    assert result["word_count"] == 12345
    assert result["chapter_titles"][0] == "第 1 章"
    assert result["chapter_titles"][-1] == "第 5 章"
