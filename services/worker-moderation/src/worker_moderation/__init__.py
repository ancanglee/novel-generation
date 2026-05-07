"""worker-moderation package.

Status: V2 reserved. The U1 platform provisions the ECS service, ECR repo,
SQS queue (`moderation-queue`), and EventBridge rule, but keeps
desired_count=0 and does not subscribe the rule until V2 activates
ModerationAgent. See aidlc-docs/construction/U5-critic/nfr-design/logical-components.md.
"""
