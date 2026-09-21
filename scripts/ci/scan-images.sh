#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"
TRIVY_IMAGE="${TRIVY_IMAGE:-aquasec/trivy:0.74.0}"

mkdir -p .ci-artifacts

docker save \
  "ciis-backend:${GIT_SHA}" \
  -o .ci-artifacts/ciis-backend.tar

docker save \
  "ciis-web:${GIT_SHA}" \
  -o .ci-artifacts/ciis-web.tar

for image_tar in ciis-backend ciis-web; do
  echo "Scanning ${image_tar}:${GIT_SHA}"

  docker run --rm \
    -v "$ROOT/.ci-artifacts:/scan" \
    -v "$ROOT/.trivyignore:/trivyignore:ro" \
    "$TRIVY_IMAGE" \
    image \
    --input "/scan/${image_tar}.tar" \
    --scanners vuln \
    --severity CRITICAL \
    --ignorefile /trivyignore \
    --exit-code 1 \
    --format json \
    --output "/scan/${image_tar}.trivy.json"
done
