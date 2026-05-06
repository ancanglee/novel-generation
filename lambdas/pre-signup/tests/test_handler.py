"""Tests for PreSignUp handler using moto."""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ["TENANCY_TABLE"] = "novelgen_dev_tenancy"
os.environ["ENV"] = "dev"

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def dynamodb_table():
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
        yield table


def test_pre_signup_creates_team_and_user(dynamodb_table):
    # Import inside fixture so the mock is active when the module constructs its boto3 client.
    with patch.dict(os.environ, {"TENANCY_TABLE": "novelgen_dev_tenancy"}):
        import importlib

        import handler as h

        importlib.reload(h)

        event = {
            "triggerSource": "PreSignUp_SignUp",
            "userName": "user-123",
            "request": {"userAttributes": {"email": "alice@example.com"}},
            "response": {},
        }
        result = h.handler(event, None)

        assert result["response"]["autoVerifyEmail"] is True
        assert "custom:team_id" in result["response"]["userAttributes"]

        items = dynamodb_table.scan()["Items"]
        assert len(items) == 2  # TEAM#META + USER#user-123


def test_non_signup_trigger_passes_through(dynamodb_table):
    with patch.dict(os.environ, {"TENANCY_TABLE": "novelgen_dev_tenancy"}):
        import importlib

        import handler as h

        importlib.reload(h)

        event = {
            "triggerSource": "PostConfirmation_ConfirmSignUp",
            "request": {"userAttributes": {}},
        }
        result = h.handler(event, None)
        assert result == event
