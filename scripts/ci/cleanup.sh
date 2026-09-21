#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Every CI compose project is build-scoped. Only these names are touched; this
# deliberately avoids broad docker prune commands that could remove developer
# or unrelated Jenkins workloads from the same Docker daemon.
RUN_ID="${BUILD_NUMBER:-$$}"

down_compose() {
  local project="$1"
  local compose_file="$2"

  docker compose \
    -p "$project" \
    -f "$compose_file" \
    down -v \
    >/dev/null 2>&1 || true
}

down_compose "${CI_DB_COMPOSE_PROJECT:-ciis-ci-db-$RUN_ID}" compose.db.yaml
down_compose "ciis-int-db-$RUN_ID" compose.db.yaml
down_compose "${CI_STORAGE_COMPOSE_PROJECT:-ciis-int-storage-$RUN_ID}" compose.storage.yaml
down_compose "${CI_QUEUE_COMPOSE_PROJECT:-ciis-int-queue-$RUN_ID}" compose.queue.yaml

for container in \
  "ciis-ci-api-$RUN_ID" \
  "ciis-ci-worker-$RUN_ID" \
  "ciis-worker-smoke-$RUN_ID" \
  ciis-api \
  ciis-frontend; do
  docker rm -f "$container" >/dev/null 2>&1 || true
done

if [ -n "${GIT_SHA:-}" ]; then
  docker image rm \
    "ciis-backend:$GIT_SHA" \
    "ciis-web:$GIT_SHA" \
    "ciis-worker:$GIT_SHA" \
    >/dev/null 2>&1 || true
fi
