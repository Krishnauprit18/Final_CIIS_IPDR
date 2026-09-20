#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:0.74.0}"

cd "$ROOT"
mkdir -p "$ARTIFACT_DIR"

scan_target() {
  local target="$1"
  local report_name="$2"

  docker run --rm \
    -v "$ROOT:/repo:ro" \
    -v "$ARTIFACT_DIR:/reports" \
    "$TRIVY_IMAGE" \
    config \
    --severity CRITICAL \
    --exit-code 1 \
    --ignorefile /repo/.trivyignore \
    --format json \
    --output "/reports/$report_name" \
    "/repo/$target"
}

# Run each target separately: Trivy treats multiple positional targets as an
# invalid invocation in the versions used by the Jenkins agent.
scan_target infra trivy-terraform.json
scan_target deploy trivy-kubernetes.json

echo "Terraform and Kubernetes IaC security checks passed."
