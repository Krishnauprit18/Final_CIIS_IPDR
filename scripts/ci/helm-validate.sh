#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"
RENDERED_FILE="$ARTIFACT_DIR/ciis-rendered.yaml"

mkdir -p "$ARTIFACT_DIR"

helm lint deploy/helm/ciis

helm template ciis deploy/helm/ciis \
  --set "image.tag=${GIT_SHA}" \
  --set config.flociIp=172.18.0.2 \
  > "$RENDERED_FILE"

grep -q 'name: ciis-api' "$RENDERED_FILE"
grep -q 'name: ciis-worker' "$RENDERED_FILE"
grep -q 'name: ciis-web' "$RENDERED_FILE"

echo "Helm validation passed: $RENDERED_FILE"
