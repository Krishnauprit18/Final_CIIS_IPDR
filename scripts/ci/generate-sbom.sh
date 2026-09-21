#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"
SYFT_IMAGE="${SYFT_IMAGE:-anchore/syft:v1.18.1}"

cd "$ROOT"
mkdir -p "$ARTIFACT_DIR"

docker save "ciis-backend:${GIT_SHA}" -o "$ARTIFACT_DIR/ciis-backend.tar"
docker save "ciis-web:${GIT_SHA}" -o "$ARTIFACT_DIR/ciis-web.tar"

docker run --rm \
  -v "$ARTIFACT_DIR:/scan:ro" \
  -v "$ARTIFACT_DIR:/reports" \
  "$SYFT_IMAGE" \
  docker-archive:/scan/ciis-backend.tar \
  -o cyclonedx-json=/reports/ciis-backend.cdx.json

docker run --rm \
  -v "$ARTIFACT_DIR:/scan:ro" \
  -v "$ARTIFACT_DIR:/reports" \
  "$SYFT_IMAGE" \
  docker-archive:/scan/ciis-web.tar \
  -o cyclonedx-json=/reports/ciis-web.cdx.json

echo "CycloneDX SBOMs generated for ${GIT_SHA}."
