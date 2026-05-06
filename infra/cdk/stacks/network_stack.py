"""01-NetworkStack: VPC / Subnets / NAT / VPC Endpoints / Security Groups."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from config import EnvConfig
from constructs import Construct


class NetworkStack(cdk.Stack):
    def __init__(self, scope: Construct, id_: str, *, cfg: EnvConfig, **kwargs) -> None:
        super().__init__(scope, id_, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"{cfg.prefix}-vpc",
            ip_addresses=ec2.IpAddresses.cidr(cfg.vpc_cidr),

            nat_gateways=1,
            # 显式列 AZ 避免 synth 时回调 AWS API；CI 环境无凭证。
            availability_zones=[f"{cfg.region}a", f"{cfg.region}b"],
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=22,
                ),
                ec2.SubnetConfiguration(
                    name="isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # Gateway endpoints (free, reduce NAT traffic)
        self.vpc.add_gateway_endpoint("S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3)
        self.vpc.add_gateway_endpoint(
            "DdbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )

        # Interface endpoints
        interface_services = {
            "SecretsMgr": ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            "Ssm": ec2.InterfaceVpcEndpointAwsService.SSM,
            "Logs": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            "Sts": ec2.InterfaceVpcEndpointAwsService.STS,
            "EcrApi": ec2.InterfaceVpcEndpointAwsService.ECR,
            "EcrDkr": ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            "Events": ec2.InterfaceVpcEndpointAwsService.EVENTBRIDGE,
            "Sqs": ec2.InterfaceVpcEndpointAwsService.SQS,
            "Sfn": ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS,
        }
        for label, svc in interface_services.items():
            self.vpc.add_interface_endpoint(f"{label}Endpoint", service=svc, private_dns_enabled=True)

        # Bedrock runtime endpoint (service name varies by region)
        self.vpc.add_interface_endpoint(
            "BedrockRuntimeEndpoint",
            service=ec2.InterfaceVpcEndpointService(
                f"com.amazonaws.{cfg.region}.bedrock-runtime", 443
            ),
            private_dns_enabled=True,
        )

        # Security groups
        self.sg_alb = ec2.SecurityGroup(
            self, "SgAlb", vpc=self.vpc, description="ALB ingress 443", allow_all_outbound=True
        )
        self.sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS public")

        self.sg_ecs_api = ec2.SecurityGroup(
            self, "SgEcsApi", vpc=self.vpc, description="API Fargate", allow_all_outbound=True
        )
        self.sg_ecs_api.add_ingress_rule(self.sg_alb, ec2.Port.tcp(8000), "API from ALB")

        self.sg_ecs_front = ec2.SecurityGroup(
            self, "SgEcsFront", vpc=self.vpc, description="Frontend BFF", allow_all_outbound=True
        )
        self.sg_ecs_front.add_ingress_rule(self.sg_alb, ec2.Port.tcp(3000), "Front from ALB")
        self.sg_ecs_front.add_ingress_rule(self.sg_alb, ec2.Port.tcp(3001), "Admin front from ALB")

        self.sg_ecs_worker = ec2.SecurityGroup(
            self, "SgEcsWorker", vpc=self.vpc, description="Workers", allow_all_outbound=True
        )

        self.sg_neptune = ec2.SecurityGroup(
            self,
            "SgNeptune",
            vpc=self.vpc,
            description="Neptune cluster",
            allow_all_outbound=False,
        )
        self.sg_neptune.add_ingress_rule(self.sg_ecs_api, ec2.Port.tcp(8182))
        self.sg_neptune.add_ingress_rule(self.sg_ecs_worker, ec2.Port.tcp(8182))

        cdk.CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
