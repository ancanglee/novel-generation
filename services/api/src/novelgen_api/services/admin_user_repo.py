"""Admin user management repository.

Queries the tenancy table for user records across all teams and wraps
Cognito admin API calls for disable / reset password / group management.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import aioboto3

from novelgen_storage import DynamoDBAdapter

_REGION = os.environ.get("AWS_REGION", "us-east-1")
_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")


class AdminUserRepo:
    """Read cross-team users + mutate via Cognito admin API."""

    def __init__(self, tenancy: DynamoDBAdapter) -> None:
        self._tenancy = tenancy
        self._session = aioboto3.Session()

    async def list_users(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """List all users by scanning USER# rows across the tenancy table."""
        rows = await self._tenancy.query_by_sk_prefix(
            team_id=None,  # type: ignore[arg-type]
            sk_prefix="USER#",
            limit=limit,
        ) if hasattr(self._tenancy, "scan_by_sk_prefix") else []
        if rows:
            return rows
        # Fallback to Cognito ListUsers (cross-team view).
        return await self._list_cognito_users(limit=limit)

    async def _list_cognito_users(self, *, limit: int) -> list[dict[str, Any]]:
        if not _USER_POOL_ID:
            return []
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            resp = await cog.list_users(UserPoolId=_USER_POOL_ID, Limit=min(limit, 60))
        users: list[dict[str, Any]] = []
        for u in resp.get("Users", []):
            attrs = {a["Name"]: a.get("Value", "") for a in u.get("Attributes", [])}
            users.append({
                "user_id": u.get("Username", ""),
                "email": attrs.get("email", ""),
                "display_name": attrs.get("preferred_username") or attrs.get("email", ""),
                "team_id": attrs.get("custom:team_id", ""),
                "global_role": attrs.get("custom:global_role", "regular_user"),
                "team_role": attrs.get("custom:team_role", "member"),
                "status": "active" if u.get("Enabled", True) else "disabled",
                "created_at": (u.get("UserCreateDate") or "").__str__(),
                "last_login_at": None,
            })
        return users

    async def disable_user(self, user_id: UUID) -> None:
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            await cog.admin_disable_user(UserPoolId=_USER_POOL_ID, Username=str(user_id))

    async def enable_user(self, user_id: UUID) -> None:
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            await cog.admin_enable_user(UserPoolId=_USER_POOL_ID, Username=str(user_id))

    async def reset_password(self, user_id: UUID) -> None:
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            await cog.admin_reset_user_password(
                UserPoolId=_USER_POOL_ID, Username=str(user_id)
            )

    async def add_to_group(self, user_id: UUID, group: str) -> None:
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            await cog.admin_add_user_to_group(
                UserPoolId=_USER_POOL_ID, Username=str(user_id), GroupName=group
            )

    async def remove_from_group(self, user_id: UUID, group: str) -> None:
        async with self._session.client("cognito-idp", region_name=_REGION) as cog:
            await cog.admin_remove_user_from_group(
                UserPoolId=_USER_POOL_ID, Username=str(user_id), GroupName=group
            )
