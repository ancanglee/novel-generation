#!/usr/bin/env bash
# Bootstrap CDK in the target AWS account + region.
# Run this once per account before the first deploy.
set -euo pipefail

ACCOUNT="${AWS_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
REGION="${AWS_REGION:-us-east-1}"

echo "Bootstrapping CDK in aws://${ACCOUNT}/${REGION}"
cd "$(dirname "$0")/../infra/cdk"
uv sync
uv run cdk bootstrap "aws://${ACCOUNT}/${REGION}"

echo "Done."
