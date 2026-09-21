#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

: "${LOCUST_HOST:?LOCUST_HOST must point to the target API}"
: "${LOCUST_USERS:?LOCUST_USERS must be set explicitly}"
: "${LOCUST_SPAWN_RATE:?LOCUST_SPAWN_RATE must be set explicitly}"

mkdir -p .ci-artifacts/performance
run_id="$(date -u +%Y%m%dT%H%M%SZ)"

python -m locust \
  -f performance/locustfile.py \
  --headless \
  --host "$LOCUST_HOST" \
  --users "$LOCUST_USERS" \
  --spawn-rate "$LOCUST_SPAWN_RATE" \
  --run-time "${LOCUST_RUN_TIME:-60s}" \
  --csv ".ci-artifacts/performance/locust-${run_id}" \
  --html ".ci-artifacts/performance/locust-${run_id}.html"

echo "Load-test evidence written under .ci-artifacts/performance/"
