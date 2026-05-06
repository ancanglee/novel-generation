"""Cognito PreSignUp Lambda trigger.

Creates a default personal Team for the new user and stores it on custom:team_id.
Runs before the user is persisted in Cognito.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

TENANCY_TABLE = os.environ["TENANCY_TABLE"]
ENV = os.environ.get("ENV", "dev")

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TENANCY_TABLE)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Cognito PreSignUp_SignUp trigger entry point."""
    trigger = event.get("triggerSource", "")
    user_attrs = event.get("request", {}).get("userAttributes", {})
    email = user_attrs.get("email", "")

    if trigger not in ("PreSignUp_SignUp", "PreSignUp_AdminCreateUser", "PreSignUp_ExternalProvider"):
        # Not a sign-up event; pass through untouched.
        return event

    team_id = str(uuid.uuid4())
    user_id = event.get("userName") or str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()

    team_pk = f"TEAM#{team_id}"
    # Write Team meta + User row atomically via TransactWriteItems
    _ddb.meta.client.transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": TENANCY_TABLE,
                    "Item": {
                        "pk": {"S": team_pk},
                        "sk": {"S": "TEAM#META"},
                        "team_id": {"S": team_id},
                        "name": {"S": email or "personal"},
                        "owner_user_id": {"S": user_id},
                        "status": {"S": "active"},
                        "created_at": {"S": now},
                    },
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            },
            {
                "Put": {
                    "TableName": TENANCY_TABLE,
                    "Item": {
                        "pk": {"S": team_pk},
                        "sk": {"S": f"USER#{user_id}"},
                        "user_id": {"S": user_id},
                        "email": {"S": email},
                        "team_id": {"S": team_id},
                        "global_role": {"S": "regular_user"},
                        "status": {"S": "active"},
                        "created_at": {"S": now},
                    },
                }
            },
        ]
    )

    # Echo team_id back to Cognito as a custom attribute. Cognito expects it in
    # response.userAttributes for PreSignUp_ExternalProvider and as a separate write path
    # for email verification. We set it here; for cases where Cognito doesn't honor this,
    # a Pre-Token-Generation trigger would inject claims.
    event.setdefault("response", {})
    event["response"]["autoConfirmUser"] = trigger == "PreSignUp_ExternalProvider"
    event["response"]["autoVerifyEmail"] = True
    event["response"]["userAttributes"] = {
        **user_attrs,
        "custom:team_id": team_id,
        "custom:team_roles": json.dumps({team_id: "owner"}),
    }

    return event
