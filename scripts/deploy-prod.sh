#!/usr/bin/env bash
# Deploy to prod — requires explicit confirmation.
set -euo pipefail

export NOVELGEN_ENV="prod"
export AWS_REGION="${AWS_REGION:-us-east-1}"

echo "You are about to deploy NovelGen to PRODUCTION in ${AWS_REGION}."
read -rp "Type 'DEPLOY-PROD' to continue: " confirm
if [[ "${confirm}" != "DEPLOY-PROD" ]]; then
    echo "Aborted."
    exit 1
fi

cd "$(dirname "$0")/../infra/cdk"
uv sync
uv run cdk deploy --all --require-approval broadening

echo ""
echo "Prod deployment complete."
