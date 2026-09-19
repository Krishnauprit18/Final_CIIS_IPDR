#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BACKEND_IMAGE="${BACKEND_IMAGE:?BACKEND_IMAGE is required}"

if docker ps --format '{{.Names}}' | grep -Eq '^(ciis-minio|ciis-localstack)$'; then
  echo "A fixed-name CI dependency container is already running." >&2
  echo "Run this script on a dedicated Jenkins agent or stop the conflicting container first." >&2
  exit 1
fi

EXISTING_POSTGRES="$(docker compose -f compose.db.yaml ps -q postgres 2>/dev/null || true)"
if [ -n "$EXISTING_POSTGRES" ]; then
  echo "A PostgreSQL Compose container already exists for this project." >&2
  echo "Run this script on a clean, dedicated Jenkins agent." >&2
  exit 1
fi

cleanup() {
  set +e
  docker rm -f ciis-ci-api ciis-ci-worker >/dev/null 2>&1 || true
  docker compose -f compose.db.yaml down >/dev/null 2>&1 || true
  docker compose -f compose.storage.yaml down >/dev/null 2>&1 || true
  docker compose -f compose.queue.yaml down >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker compose -f compose.db.yaml up -d
docker compose -f compose.storage.yaml up -d
docker compose -f compose.queue.yaml up -d

POSTGRES_CONTAINER="$(
  docker compose -f compose.db.yaml ps -q postgres
)"

if [ -z "$POSTGRES_CONTAINER" ]; then
  echo "PostgreSQL container was not created." >&2
  exit 1
fi

postgres_ready=false
for _ in $(seq 1 60); do
  if docker exec "$POSTGRES_CONTAINER" pg_isready -U ciis -d ciis; then
    postgres_ready=true
    break
  fi
  sleep 2
done

if [ "$postgres_ready" != true ]; then
  echo "PostgreSQL did not become ready within 120 seconds." >&2
  exit 1
fi

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null

export AWS_ACCESS_KEY_ID='test'
export AWS_SECRET_ACCESS_KEY='test'
export AWS_DEFAULT_REGION='us-east-1'

storage_ready=false
for _ in $(seq 1 60); do
  if aws --endpoint-url http://127.0.0.1:9000 \
      s3api head-bucket --bucket ciis-storage >/dev/null 2>&1; then
    storage_ready=true
    break
  fi
  sleep 2
done

if [ "$storage_ready" != true ]; then
  echo "MinIO bucket ciis-storage did not become ready." >&2
  exit 1
fi

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:4566/_localstack/health >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:4566/_localstack/health >/dev/null

queue_ready=false
for _ in $(seq 1 60); do
  if aws --endpoint-url http://127.0.0.1:4566 \
      sqs get-queue-url --queue-name ciis-analysis >/dev/null 2>&1; then
    queue_ready=true
    break
  fi
  sleep 2
done

if [ "$queue_ready" != true ]; then
  echo "LocalStack queue ciis-analysis did not become ready." >&2
  exit 1
fi

docker run --rm \
  --network host \
  -e DATABASE_URL='postgresql+psycopg://ciis:ciis@127.0.0.1:5432/ciis' \
  "$BACKEND_IMAGE" \
  python -m alembic upgrade head

docker run -d \
  --name ciis-ci-api \
  --network host \
  -e DATABASE_URL='postgresql+psycopg://ciis:ciis@127.0.0.1:5432/ciis' \
  -e STORAGE_ENDPOINT_URL='http://127.0.0.1:9000' \
  -e STORAGE_ACCESS_KEY='ciisadmin' \
  -e STORAGE_SECRET_KEY='ciisadmin123' \
  -e STORAGE_BUCKET='ciis-storage' \
  -e SQS_ENDPOINT_URL='http://127.0.0.1:4566' \
  -e SQS_REGION='us-east-1' \
  -e SQS_ACCESS_KEY='test' \
  -e SQS_SECRET_KEY='test' \
  -e SQS_ANALYSIS_QUEUE_NAME='ciis-analysis' \
  -e SQS_ANALYSIS_DLQ_NAME='ciis-analysis-dlq' \
  -e CIIS_ROLE='api' \
  "$BACKEND_IMAGE" >/dev/null

api_live=false
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health/live >/dev/null; then
    api_live=true
    break
  fi
  sleep 2
done

if [ "$api_live" != true ]; then
  docker logs ciis-ci-api >&2 || true
  echo "API liveness check failed." >&2
  exit 1
fi

curl -fsS http://127.0.0.1:8000/health/live >/dev/null
curl -fsS http://127.0.0.1:8000/health/ready >/dev/null

set +e
timeout 20s docker run --rm \
  --network host \
  -e DATABASE_URL='postgresql+psycopg://ciis:ciis@127.0.0.1:5432/ciis' \
  -e STORAGE_ENDPOINT_URL='http://127.0.0.1:9000' \
  -e STORAGE_ACCESS_KEY='ciisadmin' \
  -e STORAGE_SECRET_KEY='ciisadmin123' \
  -e STORAGE_BUCKET='ciis-storage' \
  -e SQS_ENDPOINT_URL='http://127.0.0.1:4566' \
  -e SQS_REGION='us-east-1' \
  -e SQS_ACCESS_KEY='test' \
  -e SQS_SECRET_KEY='test' \
  -e SQS_ANALYSIS_QUEUE_NAME='ciis-analysis' \
  -e SQS_ANALYSIS_DLQ_NAME='ciis-analysis-dlq' \
  -e WORKER_POLL_SECONDS='1' \
  -e CIIS_ROLE='worker' \
  "$BACKEND_IMAGE" \
  python -m app.workers.analysis_worker
worker_exit_code=$?
set -e

if [ "$worker_exit_code" -ne 124 ]; then
  echo "Worker smoke test failed with exit code $worker_exit_code." >&2
  exit "$worker_exit_code"
fi

echo "Container integration checks passed."
