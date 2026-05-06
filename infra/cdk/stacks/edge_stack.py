"""06-EdgeStack: CloudFront × 2 + WAF."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_wafv2 as wafv2
from config import EnvConfig
from constructs import Construct

from stacks.compute_stack import ComputeStack


class EdgeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        compute: ComputeStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        # ---- WAF ----------------------------------------------------------
        self.web_acl = wafv2.CfnWebACL(
            self,
            "WebAcl",
            name=f"{cfg.prefix}-waf",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="CLOUDFRONT",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{cfg.prefix}-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSCommonRuleSet",
                    priority=10,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS", name="AWSManagedRulesCommonRuleSet"
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="common",
                        sampled_requests_enabled=True,
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimit",
                    priority=20,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=2000, aggregate_key_type="IP"
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="rate",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )

        origin = origins.LoadBalancerV2Origin(
            compute.alb,
            protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
            http_port=80,
        )

        # User distribution
        self.user_distribution = cf.Distribution(
            self,
            "UserDistribution",
            comment=f"{cfg.prefix}-user",
            default_behavior=cf.BehaviorOptions(
                origin=origin,
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
            additional_behaviors={
                "/api/*": cf.BehaviorOptions(
                    origin=origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER,
                ),
                "/api/v1/jobs/*/stream": cf.BehaviorOptions(
                    origin=origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER,
                    compress=False,  # SSE streaming
                ),
            },
            web_acl_id=self.web_acl.attr_arn,
            price_class=cf.PriceClass.PRICE_CLASS_100,
            enabled=True,
        )

        # Admin distribution
        self.admin_distribution = cf.Distribution(
            self,
            "AdminDistribution",
            comment=f"{cfg.prefix}-admin",
            default_behavior=cf.BehaviorOptions(
                origin=origin,
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
            web_acl_id=self.web_acl.attr_arn,
            price_class=cf.PriceClass.PRICE_CLASS_100,
            enabled=True,
        )

        cdk.CfnOutput(
            self, "UserCloudFrontUrl", value=f"https://{self.user_distribution.domain_name}"
        )
        cdk.CfnOutput(
            self, "AdminCloudFrontUrl", value=f"https://{self.admin_distribution.domain_name}"
        )
