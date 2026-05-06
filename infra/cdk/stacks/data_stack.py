"""02-DataStack: DynamoDB × 4, S3 × 4, Neptune Serverless, OpenSearch Serverless, Secrets, SSM."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_neptune_alpha as neptune
from aws_cdk import aws_opensearchserverless as aoss
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import EnvConfig
from stacks.network_stack import NetworkStack


class DataStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        network: NetworkStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        removal = cdk.RemovalPolicy.DESTROY if cfg.env_name == "dev" else cdk.RemovalPolicy.RETAIN

        # ---- DynamoDB (D1=B: by-domain tables) ---------------------------
        self.tenancy_table = ddb.Table(
            self,
            "TenancyTable",
            table_name=f"{cfg.ddb_prefix}_tenancy",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
            removal_policy=removal,
        )
        self.tenancy_table.add_global_secondary_index(
            index_name="GSI-email",
            partition_key=ddb.Attribute(name="email", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.KEYS_ONLY,
        )

        self.jobs_table = ddb.Table(
            self,
            "JobsTable",
            table_name=f"{cfg.ddb_prefix}_jobs",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
            removal_policy=removal,
        )
        self.jobs_table.add_global_secondary_index(
            index_name="GSI-status",
            partition_key=ddb.Attribute(name="status", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.STRING),
        )
        self.jobs_table.add_global_secondary_index(
            index_name="GSI-user",
            partition_key=ddb.Attribute(name="owner_user_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.STRING),
        )

        self.audit_table = ddb.Table(
            self,
            "AuditTable",
            table_name=f"{cfg.ddb_prefix}_audit",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,  # audit never gets dropped
        )
        self.audit_table.add_global_secondary_index(
            index_name="GSI-actor",
            partition_key=ddb.Attribute(name="actor_user_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="timestamp", type=ddb.AttributeType.STRING),
        )

        self.config_table = ddb.Table(
            self,
            "ConfigTable",
            table_name=f"{cfg.ddb_prefix}_config",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=removal,
        )

        # ---- S3 Buckets ----------------------------------------------------
        self.novels_bucket = s3.Bucket(
            self,
            "NovelsBucket",
            bucket_name=f"{cfg.prefix}-novels",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            intelligent_tiering_configurations=[
                s3.IntelligentTieringConfiguration(name="default")
            ],
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=cdk.Duration.days(90),
                )
            ],
            removal_policy=removal,
        )

        self.exports_bucket = s3.Bucket(
            self,
            "ExportsBucket",
            bucket_name=f"{cfg.prefix}-exports",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[s3.LifecycleRule(expiration=cdk.Duration.days(30))],
            removal_policy=removal,
        )

        self.audit_archive_bucket = s3.Bucket(
            self,
            "AuditArchiveBucket",
            bucket_name=f"{cfg.prefix}-audit-archive",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_lock_enabled=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                            transition_after=cdk.Duration.days(90),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.DEEP_ARCHIVE,
                            transition_after=cdk.Duration.days(365),
                        ),
                    ]
                )
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        self.logs_bucket = s3.Bucket(
            self,
            "LogsBucket",
            bucket_name=f"{cfg.prefix}-logs",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[s3.LifecycleRule(expiration=cdk.Duration.days(90))],
            removal_policy=removal,
        )

        # ---- Neptune Serverless -------------------------------------------
        self.neptune_cluster = neptune.DatabaseCluster(
            self,
            "NeptuneCluster",
            vpc=network.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[network.sg_neptune],
            instance_type=neptune.InstanceType.SERVERLESS,
            serverless_scaling_configuration=neptune.ServerlessScalingConfiguration(
                min_capacity=1.0, max_capacity=16.0
            ),
            iam_authentication=True,
            storage_encrypted=True,
            backup_retention=cdk.Duration.days(7),
            removal_policy=removal,
        )

        # ---- OpenSearch Serverless (Vector Search) ------------------------
        self.aoss_encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "AossEncPolicy",
            name=f"{cfg.prefix}-enc",
            type="encryption",
            policy=(
                '{"Rules":[{"ResourceType":"collection","Resource":["collection/'
                f"{cfg.prefix}-vectors"
                '"]}],"AWSOwnedKey":true}'
            ),
        )
        self.aoss_network_policy = aoss.CfnSecurityPolicy(
            self,
            "AossNetPolicy",
            name=f"{cfg.prefix}-net",
            type="network",
            policy=(
                '[{"Rules":[{"ResourceType":"collection","Resource":["collection/'
                f"{cfg.prefix}-vectors"
                '"]},{"ResourceType":"dashboard","Resource":["collection/'
                f"{cfg.prefix}-vectors"
                '"]}],"AllowFromPublic":true}]'
            ),
        )
        self.aoss_collection = aoss.CfnCollection(
            self,
            "AossCollection",
            name=f"{cfg.prefix}-vectors",
            type="VECTORSEARCH",
            description="NovelGen facts & chunks vector index",
        )
        self.aoss_collection.add_dependency(self.aoss_encryption_policy)
        self.aoss_collection.add_dependency(self.aoss_network_policy)

        # ---- Secrets (D10=B: sensitive only) ------------------------------
        self.google_oauth_secret = secrets.Secret(
            self,
            "GoogleOauthSecret",
            secret_name=f"/novelgen/{cfg.env_name}/google-oauth",
            description="Google IdP client secret for Cognito",
        )
        self.github_oauth_secret = secrets.Secret(
            self,
            "GithubOauthSecret",
            secret_name=f"/novelgen/{cfg.env_name}/github-oauth",
            description="GitHub IdP client secret for Cognito",
        )
        self.cognito_app_secret = secrets.Secret(
            self,
            "CognitoAppSecret",
            secret_name=f"/novelgen/{cfg.env_name}/cognito-app-secret",
            description="Cognito App Client secret",
        )

        # ---- SSM Parameters (non-sensitive config) ------------------------
        ssm.StringParameter(
            self,
            "ParamRegion",
            parameter_name=f"/novelgen/{cfg.env_name}/config/bedrock-region",
            string_value=cfg.region,
        )
        ssm.StringParameter(
            self,
            "ParamAlertEmail",
            parameter_name=f"/novelgen/{cfg.env_name}/config/alert-email",
            string_value=cfg.alert_email,
        )
        ssm.StringParameter(
            self,
            "ParamNovelsBucket",
            parameter_name=f"/novelgen/{cfg.env_name}/config/novels-bucket",
            string_value=self.novels_bucket.bucket_name,
        )
        ssm.StringParameter(
            self,
            "ParamExportsBucket",
            parameter_name=f"/novelgen/{cfg.env_name}/config/exports-bucket",
            string_value=self.exports_bucket.bucket_name,
        )
        ssm.StringParameter(
            self,
            "ParamAossEndpoint",
            parameter_name=f"/novelgen/{cfg.env_name}/config/aoss-endpoint",
            string_value=self.aoss_collection.attr_collection_endpoint,
        )
        ssm.StringParameter(
            self,
            "ParamNeptuneEndpoint",
            parameter_name=f"/novelgen/{cfg.env_name}/config/neptune-endpoint",
            string_value=self.neptune_cluster.cluster_endpoint.socket_address,
        )

        cdk.CfnOutput(self, "NovelsBucketName", value=self.novels_bucket.bucket_name)
        cdk.CfnOutput(self, "AossCollection", value=self.aoss_collection.attr_collection_endpoint)
