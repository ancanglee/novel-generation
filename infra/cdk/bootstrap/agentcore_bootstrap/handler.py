"""CDK Custom Resource Lambda: orchestrates AgentCore control-plane operations.

Why a Lambda instead of L1 CFN: at the time of first deploy, the service's CFN
resources may not cover every field we need (namespaces on memory strategies,
workloadIdentityAuthorizer on gateway, etc.). A Lambda with boto3 lets us drive
the full API surface today while keeping drift-detection via CDK's CustomResource
lifecycle (onCreate / onUpdate / onDelete).

Inputs (ResourceProperties):
    Action: "Memory" | "Gateway" | "GatewayTarget" | "AgentRuntime" | "WorkloadIdentity"
    + action-specific fields.

Output (Data):
    ResourceId: primary identifier (memoryId / gatewayId / etc.)
    + service-specific attributes used downstream by other stacks via SSM.

All operations are idempotent: onCreate first checks for an existing resource
with the requested name; if found, returns its id without creating a new one.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

log = logging.getLogger("agentcore_bootstrap")
log.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-west-2")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """CloudFormation Custom Resource entry point.

    Delegates to helpers based on RequestType (Create/Update/Delete) and
    ResourceProperties.Action.
    """
    log.info("event: %s", json.dumps(event, default=str))
    request_type = event["RequestType"]
    props = event.get("ResourceProperties") or {}
    action = props.get("Action")

    try:
        if action == "Memory":
            return _handle_memory(request_type, props)
        if action == "WorkloadIdentity":
            return _handle_workload_identity(request_type, props)
        if action == "Gateway":
            return _handle_gateway(request_type, props)
        if action == "GatewayTarget":
            return _handle_gateway_target(request_type, props)
        if action == "AgentRuntime":
            return _handle_agent_runtime(request_type, props)
        raise ValueError(f"unknown Action: {action}")
    except Exception as e:  # noqa: BLE001
        log.exception("bootstrap_failed action=%s request=%s", action, request_type)
        raise


# -------------------------------------------------------------------- Memory

def _handle_memory(req: str, props: dict[str, Any]) -> dict[str, Any]:
    name = props["Name"]
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if req == "Delete":
        if props.get("RemovalPolicy", "RETAIN") == "DESTROY":
            existing = _find_memory_by_name(client, name)
            if existing:
                client.delete_memory(memoryId=existing["memoryId"])
        return {"PhysicalResourceId": props.get("PhysicalResourceId", name)}

    existing = _find_memory_by_name(client, name)
    if existing is None:
        strategies = props.get("Strategies") or [
            {"semanticMemoryStrategy": {"name": "novel-facts-semantic"}},
            {"summaryMemoryStrategy": {"name": "chapter-summaries"}},
        ]
        resp = client.create_memory(
            name=name,
            eventExpiryDuration=props.get("EventExpiryDays", "P365D"),
            memoryStrategies=strategies,
        )
        memory_id = resp["memoryId"]
        memory_arn = resp.get("memoryArn", f"arn:aws:bedrock-agentcore:{REGION}::memory/{memory_id}")
    else:
        memory_id = existing["memoryId"]
        memory_arn = existing.get("memoryArn", "")

    return {
        "PhysicalResourceId": memory_id,
        "Data": {"MemoryId": memory_id, "MemoryArn": memory_arn},
    }


def _find_memory_by_name(client, name: str) -> dict[str, Any] | None:
    token = None
    while True:
        kwargs = {"maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        resp = client.list_memories(**kwargs)
        for m in resp.get("memories", []) or resp.get("items", []):
            if m.get("name") == name:
                return m
        token = resp.get("nextToken")
        if not token:
            return None


# ---------------------------------------------------------- WorkloadIdentity

def _handle_workload_identity(req: str, props: dict[str, Any]) -> dict[str, Any]:
    name = props["Name"]
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if req == "Delete":
        if props.get("RemovalPolicy", "RETAIN") == "DESTROY":
            try:
                client.delete_workload_identity(name=name)
            except client.exceptions.ResourceNotFoundException:
                pass
        return {"PhysicalResourceId": name}

    try:
        resp = client.create_workload_identity(
            name=name,
            allowedResourceOauth2ReturnUrls=props.get("OAuth2ReturnUrls") or [],
        )
    except client.exceptions.ConflictException:
        resp = client.get_workload_identity(name=name)

    wid_arn = resp["workloadIdentityArn"]
    return {"PhysicalResourceId": name, "Data": {"WorkloadIdentityArn": wid_arn}}


# ------------------------------------------------------------------- Gateway

def _handle_gateway(req: str, props: dict[str, Any]) -> dict[str, Any]:
    name = props["Name"]
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if req == "Delete":
        if props.get("RemovalPolicy", "RETAIN") == "DESTROY":
            gw = _find_gateway_by_name(client, name)
            if gw:
                client.delete_gateway(gatewayIdentifier=gw["gatewayId"])
        return {"PhysicalResourceId": name}

    existing = _find_gateway_by_name(client, name)
    if existing is None:
        authorizer_config: dict[str, Any] = {
            "workloadIdentityAuthorizer": {
                "allowedWorkloadIdentityArns": [props["WorkloadIdentityArn"]]
            }
        }
        resp = client.create_gateway(
            name=name,
            protocolType=props.get("ProtocolType", "MCP"),
            roleArn=props["RoleArn"],
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=authorizer_config,
        )
        gateway_id = resp["gatewayId"]
        gateway_url = resp.get("gatewayUrl", "")
    else:
        gateway_id = existing["gatewayId"]
        gateway_url = existing.get("gatewayUrl", "")

    return {
        "PhysicalResourceId": gateway_id,
        "Data": {"GatewayId": gateway_id, "GatewayUrl": gateway_url},
    }


def _find_gateway_by_name(client, name: str) -> dict[str, Any] | None:
    token = None
    while True:
        kwargs = {"maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        resp = client.list_gateways(**kwargs)
        for g in resp.get("items", []):
            if g.get("name") == name:
                return g
        token = resp.get("nextToken")
        if not token:
            return None


# ----------------------------------------------------------- GatewayTarget

def _handle_gateway_target(req: str, props: dict[str, Any]) -> dict[str, Any]:
    name = props["Name"]
    gateway_id = props["GatewayId"]
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if req == "Delete":
        if props.get("RemovalPolicy", "RETAIN") == "DESTROY":
            existing = _find_target_by_name(client, gateway_id, name)
            if existing:
                client.delete_gateway_target(
                    gatewayIdentifier=gateway_id, targetId=existing["targetId"]
                )
        return {"PhysicalResourceId": f"{gateway_id}/{name}"}

    existing = _find_target_by_name(client, gateway_id, name)
    tool_schema = props.get("ToolSchemaInline") or []
    if existing is None:
        resp = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=name,
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": props["LambdaArn"],
                        "toolSchema": {"inlinePayload": tool_schema},
                    }
                }
            },
        )
        target_id = resp["targetId"]
    else:
        target_id = existing["targetId"]
        # Update tool schema on existing target.
        try:
            client.update_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id,
                targetConfiguration={
                    "mcp": {
                        "lambda": {
                            "lambdaArn": props["LambdaArn"],
                            "toolSchema": {"inlinePayload": tool_schema},
                        }
                    }
                },
            )
        except client.exceptions.ClientError:
            pass  # best effort on update

    return {
        "PhysicalResourceId": f"{gateway_id}/{target_id}",
        "Data": {"TargetId": target_id},
    }


def _find_target_by_name(client, gateway_id: str, name: str) -> dict[str, Any] | None:
    token = None
    while True:
        kwargs = {"gatewayIdentifier": gateway_id, "maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        resp = client.list_gateway_targets(**kwargs)
        for t in resp.get("items", []):
            if t.get("name") == name:
                return t
        token = resp.get("nextToken")
        if not token:
            return None


# -------------------------------------------------------------- AgentRuntime

def _handle_agent_runtime(req: str, props: dict[str, Any]) -> dict[str, Any]:
    name = props["Name"]
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if req == "Delete":
        if props.get("RemovalPolicy", "RETAIN") == "DESTROY":
            existing = _find_runtime_by_name(client, name)
            if existing:
                client.delete_agent_runtime(agentRuntimeId=existing["agentRuntimeId"])
        return {"PhysicalResourceId": name}

    existing = _find_runtime_by_name(client, name)
    if existing is None:
        resp = client.create_agent_runtime(
            agentRuntimeName=name,
            agentRuntimeArtifact={
                "containerConfiguration": {"containerUri": props["ContainerUri"]}
            },
            roleArn=props["RoleArn"],
            networkConfiguration={"networkMode": props.get("NetworkMode", "PUBLIC")},
            environmentVariables=props.get("Environment") or {},
        )
        runtime_id = resp["agentRuntimeId"]
        runtime_arn = resp["agentRuntimeArn"]
    else:
        runtime_id = existing["agentRuntimeId"]
        runtime_arn = existing["agentRuntimeArn"]
        # Update container if changed
        if props.get("ContainerUri"):
            try:
                client.update_agent_runtime(
                    agentRuntimeId=runtime_id,
                    agentRuntimeArtifact={
                        "containerConfiguration": {"containerUri": props["ContainerUri"]}
                    },
                )
            except client.exceptions.ClientError:
                pass

    return {
        "PhysicalResourceId": runtime_id,
        "Data": {"AgentRuntimeId": runtime_id, "AgentRuntimeArn": runtime_arn},
    }


def _find_runtime_by_name(client, name: str) -> dict[str, Any] | None:
    token = None
    while True:
        kwargs = {"maxResults": 50}
        if token:
            kwargs["nextToken"] = token
        resp = client.list_agent_runtimes(**kwargs)
        for r in resp.get("agentRuntimes", []):
            if r.get("agentRuntimeName") == name:
                return r
        token = resp.get("nextToken")
        if not token:
            return None
