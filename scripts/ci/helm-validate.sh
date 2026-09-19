#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"

helm lint deploy/helm/ciis

helm template ciis deploy/helm/ciis \
  --set "image.tag=${GIT_SHA}" \
  --set config.flociIp=172.18.0.2 \
  > /tmp/ciis-rendered.yaml

grep -q 'name: ciis-api' /tmp/ciis-rendered.yaml
grep -q 'name: ciis-worker' /tmp/ciis-rendered.yaml
grep -q 'name: ciis-web' /tmp/ciis-rendered.yaml

echo "Helm validation passed."
