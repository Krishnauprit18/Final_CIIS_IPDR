#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"
GITLEAKS_IMAGE="${GITLEAKS_IMAGE:-zricethezav/gitleaks:v8.30.1}"

cd "$ROOT"
mkdir -p "$ARTIFACT_DIR"

# The source is mounted read/write only so Gitleaks can write its report;
# no repository content is modified by the scanner.
docker run --rm \
  -v "$ROOT:/repo" \
  "$GITLEAKS_IMAGE" \
  detect \
  --source /repo \
  --redact \
  --no-banner \
  --report-format sarif \
  --report-path /repo/.ci-artifacts/gitleaks.sarif \
  --exit-code 1

echo "Secret scanning passed."
