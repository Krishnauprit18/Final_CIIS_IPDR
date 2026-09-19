#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"

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
    -v "$ROOT/.ci-artifacts:/scan:ro" \
    aquasec/trivy:0.74.0 \
    image \
    --input "/scan/${image_tar}.tar" \
    --severity CRITICAL \
    --ignore-unfixed \
    --exit-code 1
done
