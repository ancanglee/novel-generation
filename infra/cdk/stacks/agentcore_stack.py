"""08-AgentCoreStack: AgentCore Memory / Gateway / Browser / Identity / Observability / Runtime.

AgentCore does not yet have fully stable CloudFormation L1 resources in all regions at time of
writing. This stack uses AwsCustomResource to call the Control API as an escape hatch.
The concrete Memory namespaces, Gateway tool registrations, and Runtime packages are
populated by U3 / U4 / U5 when their Agents are built.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from constructs import Construct

from config import EnvConfig
from stacks.data_stack import DataStack
from stacks.identity_stack import IdentityStack


class AgentCoreStack(cdk.Stack):
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

        # NOTE: AgentCore CFN resources are in preview. Rather than failing `cdk synth`, we
        # create a placeholder custom resource that, when the API is stable, will provision:
        # - Memory namespace per env (actual team-level namespaces created at runtime by U3)
        # - Gateway tool registration hooks (U3/U4 add concrete tools)
        # - Browser session config
        # - Identity workload slot
        # - Observability project
        # - Runtime agent image references (U3/U4 push OCI images)

        # Placeholder: create an AwsCustomResource that just logs and succeeds.
        # U3+ will replace this with a real call.
        policy = cr.AwsCustomResourcePolicy.from_statements(
            [
                iam.PolicyStatement(
                    actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=["*"],
                )
            ]
        )

        self.placeholder = cr.AwsCustomResource(
            self,
            "AgentCorePlaceholder",
            on_create=cr.AwsSdkCall(
                service="Logs",
                action="describeLogGroups",
                parameters={"limit": 1},
                physical_resource_id=cr.PhysicalResourceId.of(f"{cfg.prefix}-agentcore-placeholder"),
            ),
            policy=policy,
        )

        cdk.CfnOutput(
            self,
            "AgentCoreStatus",
            value=(
                "PLACEHOLDER — configure AgentCore Memory/Gateway/Browser/Identity/Runtime/Observability "
                "via AgentCore console or fill this stack when CFN resources GA."
            ),
        )
