#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"

echo "Building CIIS images for Git SHA: $GIT_SHA"

docker build \
  --pull \
  --build-arg "APT_SECURITY_REFRESH=${GIT_SHA}" \
  -t "ciis-backend:${GIT_SHA}" \
  backend

docker build \
  --pull \
  --build-arg "APK_SECURITY_REFRESH=${GIT_SHA}" \
  --build-arg REACT_APP_API_BASE_URL=/api \
  -t "ciis-web:${GIT_SHA}" \
  frontend

echo "Built:"
echo "  ciis-backend:${GIT_SHA}"
echo "  ciis-web:${GIT_SHA}"
