"""06a-WafStack: WAFv2 WebACL (scope=CLOUDFRONT).

CloudFront-scoped WAF WebACLs must be deployed in us-east-1. This stack is
region-pinned to us-east-1 and exposes the ACL ARN for the EdgeStack (which
lives in the primary region) to consume via cross-region references.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_wafv2 as wafv2
from config import EnvConfig
from constructs import Construct


class WafStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

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

        cdk.CfnOutput(self, "WebAclArn", value=self.web_acl.attr_arn)
