# NovelGen CDK (Python)

8 layered stacks per U1 Infrastructure Design:

1. `network` — VPC, subnets, NAT, VPC endpoints, security groups
2. `data` — DynamoDB ×4, S3 ×4, Neptune Serverless, OpenSearch Serverless, Secrets, SSM
3. `identity` — Cognito User Pool + Google/GitHub IdP + IAM Roles + PreSignUp λ
4. `messaging` — SQS ×10, EventBridge rules, Step Functions state machine skeletons
5. `compute` — ECS Cluster, ECR ×8, 8 Fargate services (Spot for workers), ALB + TG + rules
6. `edge` — CloudFront ×2 (user + admin), WAF
7. `observability` — CloudWatch log groups, metric filters, alarms → SNS, daily aggregator/archiver λ
8. `agentcore` — AgentCore placeholder (replace when CFN resources GA)

## Commands

```bash
cd infra/cdk
uv sync
cdk bootstrap aws://ACCOUNT/us-east-1
cdk synth --all
cdk deploy --all --require-approval never   # dev only
```

## Environment variables

- `AWS_REGION` (default `us-east-1`)
- `NOVELGEN_ENV` (default `dev`)
- `NOVELGEN_VPC_CIDR` (default `10.20.0.0/16`)
- `NOVELGEN_ALERT_EMAIL` (default `admin@example.com`)

## Known caveats

- AgentCore stack is a placeholder (see `stacks/agentcore_stack.py`).
- `IdentityStack` uses placeholder OIDC issuer for GitHub; wire real OAuth client ID/secret via `google-client-id` SSM parameter + secrets post-deploy.
- `ComputeStack` references `public.ecr.aws/amazonlinux` images; replace with per-service images after first `docker build && docker push` to ECR.
- Neptune Serverless IAM auth: callers must SigV4-sign requests (handled in U3 MemoryFacade).
- ALB currently HTTP-only; add ACM cert + HTTPS listener for prod.
