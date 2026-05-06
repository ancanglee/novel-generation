"""03-IdentityStack: Cognito User Pool + IdP + IAM Roles."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from config import EnvConfig
from stacks.data_stack import DataStack


class IdentityStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        data: DataStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        # ---- PreSignUp Lambda (auto-create Team on first sign-up) ---------
        self.pre_signup_fn = _lambda.Function(
            self,
            "PreSignUpFn",
            function_name=f"{cfg.prefix}-pre-signup",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../../lambdas/pre-signup"),
            timeout=cdk.Duration.seconds(10),
            environment={
                "TENANCY_TABLE": data.tenancy_table.table_name,
                "ENV": cfg.env_name,
            },
        )
        data.tenancy_table.grant_read_write_data(self.pre_signup_fn)

        # ---- User Pool ----------------------------------------------------
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"{cfg.prefix}-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=False,
                require_digits=True,
                require_symbols=False,
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=False)
            ),
            custom_attributes={
                "team_id": cognito.StringAttribute(mutable=True),
                "team_roles": cognito.StringAttribute(mutable=True, max_len=2048),
            },
            lambda_triggers=cognito.UserPoolTriggers(pre_sign_up=self.pre_signup_fn),
            removal_policy=cdk.RemovalPolicy.DESTROY if cfg.env_name == "dev" else cdk.RemovalPolicy.RETAIN,
        )

        # Cognito Groups
        cognito.CfnUserPoolGroup(self, "AdminGroup", group_name="admin", user_pool_id=self.user_pool.user_pool_id)
        cognito.CfnUserPoolGroup(
            self,
            "ModeratorGroup",
            group_name="content_moderator",
            user_pool_id=self.user_pool.user_pool_id,
        )

        # ---- Identity Providers (Google / GitHub) -------------------------
        cognito.UserPoolIdentityProviderGoogle(
            self,
            "GoogleIdP",
            user_pool=self.user_pool,
            client_id=ssm.StringParameter.value_for_string_parameter(
                self, f"/novelgen/{cfg.env_name}/config/google-client-id", 1
            ) if False else "placeholder-client-id",  # wired manually post-deploy
            client_secret_value=data.google_oauth_secret.secret_value,
            scopes=["email", "openid", "profile"],
            attribute_mapping=cognito.AttributeMapping(email=cognito.ProviderAttribute.GOOGLE_EMAIL),
        )

        # GitHub is not a native Cognito IdP; wire as OIDC generic
        cognito.UserPoolIdentityProviderOidc(
            self,
            "GithubIdP",
            user_pool=self.user_pool,
            name="GitHub",
            client_id="placeholder",
            client_secret=data.github_oauth_secret.secret_value.unsafe_unwrap(),
            issuer_url="https://token.actions.githubusercontent.com",  # placeholder; swap to github OAuth broker URL
            attribute_request_method=cognito.OidcAttributeRequestMethod.GET,
            scopes=["openid", "email"],
        )

        # ---- App Client ---------------------------------------------------
        self.app_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name=f"{cfg.prefix}-webapp",
            generate_secret=False,  # Browser SPA (PKCE)
            auth_flows=cognito.AuthFlow(user_srp=True, admin_user_password=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=["https://example.cloudfront.net/callback"],
                logout_urls=["https://example.cloudfront.net/logout"],
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
                cognito.UserPoolClientIdentityProvider.GOOGLE,
                cognito.UserPoolClientIdentityProvider.custom("GitHub"),
            ],
            prevent_user_existence_errors=True,
        )

        # ---- IAM Roles ----------------------------------------------------
        self.ecs_exec_role = iam.Role(
            self,
            "EcsTaskExecRole",
            role_name=f"{cfg.prefix}-ecs-exec",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        self.api_task_role = iam.Role(
            self,
            "ApiTaskRole",
            role_name=f"{cfg.prefix}-api-task",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        for table in [data.tenancy_table, data.jobs_table, data.config_table]:
            table.grant_read_write_data(self.api_task_role)
        data.audit_table.grant_read_data(self.api_task_role)
        for bucket in [data.novels_bucket, data.exports_bucket]:
            bucket.grant_read_write(self.api_task_role)
        self.api_task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "states:StartExecution",
                    "states:DescribeExecution",
                    "events:PutEvents",
                    "secretsmanager:GetSecretValue",
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath",
                ],
                resources=["*"],
            )
        )

        # Audit write role (IAM write lock: only PutItem)
        self.audit_write_role = iam.Role(
            self,
            "AuditWriteRole",
            role_name=f"{cfg.prefix}-audit-write",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        self.audit_write_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem"],
                resources=[data.audit_table.table_arn],
            )
        )
        # Api task can assume audit-write
        self.audit_write_role.grant_assume_role(self.api_task_role)

        # Worker task roles
        self.worker_roles: dict[str, iam.Role] = {}
        worker_types = ["analysis", "generation", "critic", "consistency", "moderation"]
        for wt in worker_types:
            role = iam.Role(
                self,
                f"Worker{wt.capitalize()}Role",
                role_name=f"{cfg.prefix}-worker-{wt}",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            )
            for table in [data.tenancy_table, data.jobs_table, data.config_table]:
                table.grant_read_write_data(role)
            for bucket in [data.novels_bucket, data.exports_bucket]:
                bucket.grant_read_write(role)
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                        "bedrock-agentcore:*",
                        "events:PutEvents",
                        "neptune-db:*",
                        "aoss:APIAccessAll",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "states:SendTaskSuccess",
                        "states:SendTaskFailure",
                        "secretsmanager:GetSecretValue",
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath",
                    ],
                    resources=["*"],
                )
            )
            self.worker_roles[wt] = role

        self.sfn_role = iam.Role(
            self,
            "SfnExecRole",
            role_name=f"{cfg.prefix}-sfn-exec",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )
        self.sfn_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "lambda:InvokeFunction",
                    "events:PutEvents",
                    "dynamodb:UpdateItem",
                    "dynamodb:GetItem",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        cdk.CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        cdk.CfnOutput(self, "AppClientId", value=self.app_client.user_pool_client_id)
