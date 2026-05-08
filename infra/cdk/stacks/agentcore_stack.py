"""08-AgentCoreStack: real AgentCore resources (Memory / Gateway / Targets / Runtimes / WorkloadIdentity).

All resources are provisioned through a single CDK Custom Resource Lambda
(`bootstrap/agentcore_bootstrap/handler.py`) that talks to `bedrock-agentcore-control`.

Stack outputs:
- SSM parameters under `/novelgen/{env}/agentcore/*` recording resource IDs/ARNs
  so that Worker services can resolve them at runtime.
- `CfnOutput` for each resource for human ops visibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from aws_cdk import custom_resources as cr
from config import EnvConfig
from constructs import Construct

from stacks.data_stack import DataStack
from stacks.identity_stack import IdentityStack


_GATEWAY_LAMBDA_DIRS = {
    "memory-facade": "gateway-memory-facade",
    "ddb-jobs": "gateway-ddb-jobs",
    "ingestion-fetch": "gateway-ingestion-fetch",
    "ingestion-browser": "gateway-ingestion-browser",
    "graph-ops": "gateway-graph-ops",
    "vector-ops": "gateway-vector-ops",
}


def _load_tool_schema(target: str) -> list[dict[str, Any]]:
    """Load the MCP tool schema for a given target from the design doc mapping."""
    schemas: dict[str, list[dict[str, Any]]] = {
        "memory-facade": [
            {
                "name": "remember",
                "description": "Persist facts into AgentCore Memory (+ graph/vector best-effort)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "team_id": {"type": "string"},
                        "novel_id": {"type": "string"},
                        "facts": {"type": "array"},
                        "session_id": {"type": "string"},
                    },
                    "required": ["team_id", "novel_id", "facts"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "recall",
                "description": "Retrieve facts for a natural-language query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "team_id": {"type": "string"},
                        "novel_id": {"type": "string"},
                        "query": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["team_id", "novel_id", "query"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_character",
                "description": "Get character snapshot at or before a given chapter",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "team_id": {"type": "string"},
                        "novel_id": {"type": "string"},
                        "character_id": {"type": "string"},
                        "at_chapter": {"type": "integer"},
                    },
                    "required": ["team_id", "novel_id", "character_id"],
                    "additionalProperties": False,
                },
            },
        ],
        "ddb-jobs": [
            {"name": "put_checkpoint", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "get_checkpoint", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "advance_scan_cursor", "inputSchema": {"type": "object", "additionalProperties": True}},
        ],
        "ingestion-fetch": [
            {"name": "fetch_public_domain", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "fetch_url", "inputSchema": {"type": "object", "additionalProperties": True}},
        ],
        "ingestion-browser": [
            {"name": "render_with_browser", "inputSchema": {"type": "object", "additionalProperties": True}},
        ],
        "graph-ops": [
            {"name": "upsert_node", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "upsert_edge", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "neighbors", "inputSchema": {"type": "object", "additionalProperties": True}},
        ],
        "vector-ops": [
            {"name": "index_vector", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "search_similar", "inputSchema": {"type": "object", "additionalProperties": True}},
            {"name": "hybrid_search", "inputSchema": {"type": "object", "additionalProperties": True}},
        ],
    }
    return schemas[target]


class AgentCoreStack(cdk.Stack):
    """Orchestrate AgentCore Memory / Gateway / Targets / Runtimes / WorkloadIdentity."""

    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        data: DataStack,
        identity: IdentityStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        removal = (
            cdk.RemovalPolicy.DESTROY if cfg.env_name == "dev" else cdk.RemovalPolicy.RETAIN
        )
        removal_str = "DESTROY" if cfg.env_name == "dev" else "RETAIN"

        # ---- Bootstrap Lambda -------------------------------------------
        bootstrap_fn = _lambda.Function(
            self,
            "AgentCoreBootstrapFn",
            function_name=f"{cfg.prefix}-agentcore-bootstrap",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parent.parent / "bootstrap" / "agentcore_bootstrap")
            ),
            timeout=cdk.Duration.minutes(5),
            memory_size=1024,
            log_retention=logs.RetentionDays.ONE_MONTH,
            environment={"ENV": cfg.env_name},
        )
        bootstrap_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore-control:CreateMemory",
                    "bedrock-agentcore-control:GetMemory",
                    "bedrock-agentcore-control:ListMemories",
                    "bedrock-agentcore-control:UpdateMemory",
                    "bedrock-agentcore-control:DeleteMemory",
                    "bedrock-agentcore-control:CreateWorkloadIdentity",
                    "bedrock-agentcore-control:GetWorkloadIdentity",
                    "bedrock-agentcore-control:DeleteWorkloadIdentity",
                    "bedrock-agentcore-control:CreateGateway",
                    "bedrock-agentcore-control:ListGateways",
                    "bedrock-agentcore-control:DeleteGateway",
                    "bedrock-agentcore-control:CreateGatewayTarget",
                    "bedrock-agentcore-control:ListGatewayTargets",
                    "bedrock-agentcore-control:UpdateGatewayTarget",
                    "bedrock-agentcore-control:DeleteGatewayTarget",
                    "bedrock-agentcore-control:CreateAgentRuntime",
                    "bedrock-agentcore-control:GetAgentRuntime",
                    "bedrock-agentcore-control:ListAgentRuntimes",
                    "bedrock-agentcore-control:UpdateAgentRuntime",
                    "bedrock-agentcore-control:DeleteAgentRuntime",
                    "iam:PassRole",
                ],
                resources=["*"],
            )
        )

        provider = cr.Provider(
            self,
            "AgentCoreProvider",
            on_event_handler=bootstrap_fn,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # ---- WorkloadIdentity -------------------------------------------
        wid_name = f"novelgen-{cfg.env_name}-agent-workload"
        wid_cr = cdk.CustomResource(
            self,
            "WorkloadIdentityCR",
            service_token=provider.service_token,
            properties={
                "Action": "WorkloadIdentity",
                "Name": wid_name,
                "OAuth2ReturnUrls": [],
                "RemovalPolicy": removal_str,
            },
        )
        wid_arn = wid_cr.get_att_string("WorkloadIdentityArn")

        ssm.StringParameter(
            self,
            "WidArnSsm",
            parameter_name=f"/novelgen/{cfg.env_name}/agentcore/workload-identity-arn",
            string_value=wid_arn,
        )

        # ---- Memory -----------------------------------------------------
        memory_name = f"novelgen-{cfg.env_name}-memory"
        memory_cr = cdk.CustomResource(
            self,
            "MemoryCR",
            service_token=provider.service_token,
            properties={
                "Action": "Memory",
                "Name": memory_name,
                "EventExpiryDays": "P365D",
                "Strategies": [
                    {
                        "semanticMemoryStrategy": {
                            "name": "novel-facts-semantic",
                            "namespaces": ["{actorId}/{sessionId}", "{actorId}"],
                        }
                    },
                    {
                        "summaryMemoryStrategy": {
                            "name": "chapter-summaries",
                            "namespaces": ["{actorId}/chapters"],
                        }
                    },
                ],
                "RemovalPolicy": removal_str,
            },
        )
        memory_id = memory_cr.get_att_string("MemoryId")
        memory_arn = memory_cr.get_att_string("MemoryArn")

        ssm.StringParameter(
            self,
            "MemoryIdSsm",
            parameter_name=f"/novelgen/{cfg.env_name}/agentcore/memory-id",
            string_value=memory_id,
        )
        ssm.StringParameter(
            self,
            "MemoryArnSsm",
            parameter_name=f"/novelgen/{cfg.env_name}/agentcore/memory-arn",
            string_value=memory_arn,
        )

        # ---- Gateway Role -----------------------------------------------
        gateway_role = iam.Role(
            self,
            "GatewayRole",
            role_name=f"{cfg.prefix}-gateway-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
        )

        # ---- Gateway Target Lambdas -------------------------------------
        lambdas_base = Path(__file__).resolve().parent.parent.parent.parent / "lambdas"
        target_lambdas: dict[str, _lambda.Function] = {}
        for tool_name, dir_name in _GATEWAY_LAMBDA_DIRS.items():
            asset_path = str(lambdas_base / dir_name)
            env_vars: dict[str, str] = {"ENV": cfg.env_name}
            if tool_name == "memory-facade":
                env_vars["AGENTCORE_MEMORY_ID"] = memory_id
            if tool_name == "ddb-jobs":
                env_vars["JOBS_TABLE"] = data.jobs_table.table_name
            if tool_name == "ingestion-browser":
                env_vars["AGENTCORE_BROWSER_IDENTIFIER"] = "DEFAULT"
            if tool_name == "graph-ops":
                env_vars["NEPTUNE_ENDPOINT"] = cdk.Fn.import_value(
                    f"{cfg.prefix}-neptune-endpoint"
                ) if False else ""  # placeholder wiring; real stack passes it via constructor later
            if tool_name == "vector-ops":
                env_vars["OPENSEARCH_ENDPOINT"] = ""

            fn = _lambda.Function(
                self,
                f"GwLambda{dir_name.title().replace('-', '')}",
                function_name=f"{cfg.prefix}-gateway-{tool_name}",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="handler.handler",
                code=_lambda.Code.from_asset(asset_path),
                timeout=cdk.Duration.seconds(30),
                memory_size=1024,
                log_retention=logs.RetentionDays.ONE_MONTH,
                environment=env_vars,
            )
            # Permissions
            if tool_name == "memory-facade":
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=[
                            "bedrock-agentcore:CreateEvent",
                            "bedrock-agentcore:RetrieveMemoryRecords",
                            "bedrock-agentcore:ListEvents",
                        ],
                        resources=["*"],
                    )
                )
            if tool_name == "ddb-jobs":
                data.jobs_table.grant_read_write_data(fn)
            if tool_name == "ingestion-browser":
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=[
                            "bedrock-agentcore:StartBrowserSession",
                            "bedrock-agentcore:StopBrowserSession",
                            "bedrock-agentcore:GetBrowserSession",
                        ],
                        resources=["*"],
                    )
                )
            if tool_name == "graph-ops":
                fn.add_to_role_policy(
                    iam.PolicyStatement(actions=["neptune-db:*"], resources=["*"])
                )
            if tool_name == "vector-ops":
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["aoss:APIAccessAll", "aoss:BatchGetCollection"],
                        resources=["*"],
                    )
                )

            # Gateway invokes this lambda
            fn.grant_invoke(gateway_role)
            target_lambdas[tool_name] = fn

        # ---- Gateway ----------------------------------------------------
        gateway_name = f"novelgen-{cfg.env_name}-gateway"
        gateway_cr = cdk.CustomResource(
            self,
            "GatewayCR",
            service_token=provider.service_token,
            properties={
                "Action": "Gateway",
                "Name": gateway_name,
                "ProtocolType": "MCP",
                "RoleArn": gateway_role.role_arn,
                "WorkloadIdentityArn": wid_arn,
                "RemovalPolicy": removal_str,
            },
        )
        gateway_id = gateway_cr.get_att_string("GatewayId")
        gateway_url = gateway_cr.get_att_string("GatewayUrl")

        ssm.StringParameter(
            self,
            "GatewayIdSsm",
            parameter_name=f"/novelgen/{cfg.env_name}/agentcore/gateway-id",
            string_value=gateway_id,
        )
        ssm.StringParameter(
            self,
            "GatewayUrlSsm",
            parameter_name=f"/novelgen/{cfg.env_name}/agentcore/gateway-endpoint",
            string_value=gateway_url,
        )

        # ---- Gateway Targets -------------------------------------------
        for tool_name, fn in target_lambdas.items():
            tgt_cr = cdk.CustomResource(
                self,
                f"GwTarget{tool_name.title().replace('-', '')}CR",
                service_token=provider.service_token,
                properties={
                    "Action": "GatewayTarget",
                    "GatewayId": gateway_id,
                    "Name": tool_name,
                    "LambdaArn": fn.function_arn,
                    "ToolSchemaInline": _load_tool_schema(tool_name),
                    "RemovalPolicy": removal_str,
                    # Force update when schema changes
                    "SchemaHash": json.dumps(_load_tool_schema(tool_name), sort_keys=True),
                },
            )
            tgt_cr.node.add_dependency(gateway_cr)

        # ---- Agent Runtimes (5) ----------------------------------------
        # One runtime per supervisor role. Container URI is resolved from the
        # existing ECR repos (populated via CI/CD). We use "latest" for V1; CI
        # can flip to immutable SHA tags by setting cfg.agent_runtime_tag.
        runtime_tag = "latest"
        repos = {
            "supervisor-understanding": f"novelgen/worker-analysis",
            "supervisor-generation": f"novelgen/worker-generation",
            "critic": f"novelgen/worker-critic",
            "consistency": f"novelgen/worker-consistency",
            "moderation": f"novelgen/worker-moderation",
        }
        for role_name, repo_suffix in repos.items():
            runtime_name = f"novelgen-{cfg.env_name}-{role_name}"
            container_uri = (
                f"{cfg.account}.dkr.ecr.{cfg.region}.amazonaws.com/{repo_suffix}:{runtime_tag}"
            )
            # Pick the corresponding worker role (strip the "supervisor-" prefix).
            base_role = role_name.replace("supervisor-", "")
            # Map to the 5 worker roles created in IdentityStack.
            worker_role_key = {
                "understanding": "analysis",
                "generation": "generation",
                "critic": "critic",
                "consistency": "consistency",
                "moderation": "moderation",
            }[base_role]

            runtime_role = identity.worker_roles[worker_role_key]

            rt_cr = cdk.CustomResource(
                self,
                f"Runtime{role_name.title().replace('-', '')}CR",
                service_token=provider.service_token,
                properties={
                    "Action": "AgentRuntime",
                    "Name": runtime_name,
                    "ContainerUri": container_uri,
                    "RoleArn": runtime_role.role_arn,
                    "NetworkMode": "PUBLIC",
                    "Environment": {
                        "ENV": cfg.env_name,
                        "AGENTCORE_MEMORY_ID": memory_id,
                        "AGENTCORE_WORKLOAD_NAME": wid_name,
                        "AGENTCORE_GATEWAY_URL": gateway_url,
                    },
                    "RemovalPolicy": removal_str,
                },
            )
            ssm.StringParameter(
                self,
                f"RuntimeArn{role_name.title().replace('-', '')}Ssm",
                parameter_name=f"/novelgen/{cfg.env_name}/agentcore/runtime/{role_name}-arn",
                string_value=rt_cr.get_att_string("AgentRuntimeArn"),
            )

        # ---- Outputs ----------------------------------------------------
        cdk.CfnOutput(self, "MemoryIdOut", value=memory_id)
        cdk.CfnOutput(self, "GatewayIdOut", value=gateway_id)
        cdk.CfnOutput(self, "GatewayEndpointOut", value=gateway_url)
        cdk.CfnOutput(self, "WorkloadIdentityArnOut", value=wid_arn)
