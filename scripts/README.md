# Operational Scripts

| Script | Purpose |
|---|---|
| `bootstrap-cdk.sh` | One-time CDK bootstrap per AWS account |
| `deploy-dev.sh` | Deploy all 8 stacks to dev (auto-approve) |
| `deploy-prod.sh` | Deploy to prod with explicit `DEPLOY-PROD` confirmation |
| `check-code-quality.sh` | Local mirror of CI: ruff + pytest + cdk synth |

All scripts respect `AWS_REGION`, `AWS_PROFILE`, and `NOVELGEN_ENV` environment variables.
