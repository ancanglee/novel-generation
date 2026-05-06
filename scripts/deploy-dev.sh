#!/usr/bin/env bash
# Deploy all 8 stacks to the dev AWS account.
# Prerequisites: bootstrap-cdk.sh has been run; AWS_PROFILE configured.
set -euo pipefail

export NOVELGEN_ENV="${NOVELGEN_ENV:-dev}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Deploying NovelGen to ${NOVELGEN_ENV} in ${AWS_REGION}..."

cd "$(dirname "$0")/../infra/cdk"
uv sync
uv run cdk deploy --all --require-approval never

echo ""
echo "Deployment complete. Useful outputs above (CloudFront URLs, ALB DNS, Cognito IDs)."
