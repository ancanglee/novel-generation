"""06-EdgeStack: CloudFront × 2 + WAF.

WAF WebACL (scope=CLOUDFRONT) lives in the companion WafStack (us-east-1);
its ARN is injected here via cross-region references.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from config import EnvConfig
from constructs import Construct

from stacks.compute_stack import ComputeStack
from stacks.waf_stack import WafStack


class EdgeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        compute: ComputeStack,
        waf: WafStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        web_acl_arn = waf.web_acl.attr_arn

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
            web_acl_id=web_acl_arn,
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
            web_acl_id=web_acl_arn,
            price_class=cf.PriceClass.PRICE_CLASS_100,
            enabled=True,
        )

        cdk.CfnOutput(
            self, "UserCloudFrontUrl", value=f"https://{self.user_distribution.domain_name}"
        )
        cdk.CfnOutput(
            self, "AdminCloudFrontUrl", value=f"https://{self.admin_distribution.domain_name}"
        )
