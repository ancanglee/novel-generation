"""Gateway control plane wrapper (CreateGateway / CreateGatewayTarget / List...)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aioboto3


@dataclass(frozen=True)
class GatewayDescribe:
    gateway_id: str
    gateway_arn: str
    endpoint: str | None
    status: str


@dataclass(frozen=True)
class GatewayTargetDescribe:
    target_id: str
    gateway_id: str
    name: str
    status: str


class GatewayControlClient:
    """Async wrapper around `bedrock-agentcore-control` for Gateway resources."""

    def __init__(self, region: str = "us-west-2") -> None:
        self._region = region
        self._session = aioboto3.Session()

    async def ensure_gateway(
        self,
        *,
        name: str,
        role_arn: str,
        workload_identity_arn: str,
        protocol_type: str = "MCP",
    ) -> GatewayDescribe:
        """Create Gateway if absent, else return existing.

        Uses workloadIdentityAuthorizer so only tokens issued by our Workload can call it.
        """
        existing = await self._find_gateway_by_name(name)
        if existing is not None:
            return existing

        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            resp = await ctl.create_gateway(
                name=name,
                protocolType=protocol_type,
                roleArn=role_arn,
                authorizerType="AWS_IAM",  # fallback; in practice the Gateway authorizer
                # configuration is explicit below
                authorizerConfiguration={
                    "workloadIdentityAuthorizer": {
                        "allowedWorkloadIdentityArns": [workload_identity_arn]
                    }
                },
            )
        return GatewayDescribe(
            gateway_id=resp["gatewayId"],
            gateway_arn=resp["gatewayArn"],
            endpoint=resp.get("gatewayUrl"),
            status=resp.get("status", "CREATING"),
        )

    async def _find_gateway_by_name(self, name: str) -> GatewayDescribe | None:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            token: str | None = None
            while True:
                kwargs: dict[str, Any] = {"maxResults": 50}
                if token:
                    kwargs["nextToken"] = token
                resp = await ctl.list_gateways(**kwargs)
                for g in resp.get("items", []):
                    if g.get("name") == name:
                        return GatewayDescribe(
                            gateway_id=g["gatewayId"],
                            gateway_arn=g["gatewayArn"],
                            endpoint=g.get("gatewayUrl"),
                            status=g.get("status", "UNKNOWN"),
                        )
                token = resp.get("nextToken")
                if not token:
                    return None

    async def ensure_target(
        self,
        *,
        gateway_id: str,
        name: str,
        lambda_arn: str,
        tool_schema_inline: list[dict[str, Any]],
    ) -> GatewayTargetDescribe:
        """Create GatewayTarget (lambda-backed MCP tools) if absent, else return existing."""
        existing = await self._find_target_by_name(gateway_id, name)
        if existing is not None:
            return existing

        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            resp = await ctl.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=name,
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": lambda_arn,
                            "toolSchema": {"inlinePayload": tool_schema_inline},
                        }
                    }
                },
            )
        return GatewayTargetDescribe(
            target_id=resp["targetId"],
            gateway_id=gateway_id,
            name=name,
            status=resp.get("status", "CREATING"),
        )

    async def _find_target_by_name(
        self, gateway_id: str, name: str
    ) -> GatewayTargetDescribe | None:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            token: str | None = None
            while True:
                kwargs: dict[str, Any] = {"gatewayIdentifier": gateway_id, "maxResults": 50}
                if token:
                    kwargs["nextToken"] = token
                resp = await ctl.list_gateway_targets(**kwargs)
                for t in resp.get("items", []):
                    if t.get("name") == name:
                        return GatewayTargetDescribe(
                            target_id=t["targetId"],
                            gateway_id=gateway_id,
                            name=name,
                            status=t.get("status", "UNKNOWN"),
                        )
                token = resp.get("nextToken")
                if not token:
                    return None

    async def delete_gateway(self, gateway_id: str) -> None:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            await ctl.delete_gateway(gatewayIdentifier=gateway_id)
