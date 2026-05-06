#!/usr/bin/env bash
# Aggregate local lint + test + synth, mirror what CI runs.
set -euo pipefail

echo "=== ruff check ==="
uv run ruff check .
echo "=== ruff format check ==="
uv run ruff format --check .
echo "=== pytest ==="
uv run pytest -ra
echo "=== cdk synth ==="
cd infra/cdk && uv run cdk synth --all --quiet > /dev/null
echo ""
echo "All checks passed."
