#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:0.74.0}"

cd "$ROOT"
mkdir -p "$ARTIFACT_DIR"

# IaC misconfiguration is scanned separately by security-iac.sh so the
# local Floci exceptions remain scoped to Terraform only.
docker run --rm \
  -v "$ROOT:/repo:ro" \
  -v "$ARTIFACT_DIR:/reports" \
  "$TRIVY_IMAGE" \
  fs \
  --scanners vuln,secret \
  --severity CRITICAL \
  --exit-code 1 \
  --skip-dirs /repo/.git \
  --skip-dirs /repo/.venv \
  --skip-dirs /repo/.ci-venv \
  --skip-dirs /repo/frontend/node_modules \
  --skip-dirs /repo/frontend/build \
  --skip-dirs /repo/data/floci \
  --skip-dirs /repo/.ci-artifacts \
  --skip-files '/repo/infra/terraform/environments/local/terraform.tfstate*' \
  --format json \
  --output /reports/trivy-filesystem.json \
  /repo

echo "Trivy filesystem security check passed."
