#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD)}"

REGISTRY="${ECR_REGISTRY:-000000000000.dkr.ecr.us-east-1.localhost:4566}"

export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"

aws ecr get-login-password \
  | docker login \
      --username AWS \
      --password-stdin "$REGISTRY"

for repo_name in ciis-api ciis-worker ciis-web; do
  aws ecr describe-repositories \
    --repository-names "$repo_name" \
    >/dev/null
done

push_if_missing() {
  local repo_name="$1"
  local source_image="$2"
  local target="$REGISTRY/$repo_name:$GIT_SHA"

  if aws ecr describe-images \
      --repository-name "$repo_name" \
      --image-ids "imageTag=$GIT_SHA" \
      >/dev/null 2>&1; then

    echo "$target already exists; immutable tag preserved."
    return
  fi

  docker tag "$source_image" "$target"
  docker push "$target"
}

push_if_missing \
  ciis-api \
  "ciis-backend:$GIT_SHA"

push_if_missing \
  ciis-worker \
  "ciis-backend:$GIT_SHA"

push_if_missing \
  ciis-web \
  "ciis-web:$GIT_SHA"

echo "Immutable Git-SHA images published."
