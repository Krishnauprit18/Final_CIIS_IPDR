#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BACKEND_IMAGE="${BACKEND_IMAGE:?BACKEND_IMAGE is required}"
RUN_ID="${BUILD_NUMBER:-$$}"

DB_PROJECT="${CI_DB_COMPOSE_PROJECT:-ciis-int-db-$RUN_ID}"
STORAGE_PROJECT="${CI_STORAGE_COMPOSE_PROJECT:-ciis-int-storage-$RUN_ID}"
QUEUE_PROJECT="${CI_QUEUE_COMPOSE_PROJECT:-ciis-int-queue-$RUN_ID}"

free_port() {
  python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

CI_POSTGRES_PORT="${CI_POSTGRES_PORT:-$(free_port)}"
CI_MINIO_PORT="${CI_MINIO_PORT:-$(free_port)}"
CI_MINIO_CONSOLE_PORT="${CI_MINIO_CONSOLE_PORT:-$(free_port)}"
CI_LOCALSTACK_PORT="${CI_LOCALSTACK_PORT:-$(free_port)}"
CI_API_PORT="${CI_API_PORT:-$(free_port)}"

export CI_POSTGRES_PORT
export CI_MINIO_PORT
export CI_MINIO_CONSOLE_PORT
export CI_LOCALSTACK_PORT

cleanup() {
  set +e
  docker rm -f ciis-ci-api-$RUN_ID >/dev/null 2>&1 || true
  docker compose -p "$DB_PROJECT" -f compose.db.yaml down -v >/dev/null 2>&1 || true
  docker compose -p "$STORAGE_PROJECT" -f compose.storage.yaml down -v >/dev/null 2>&1 || true
  docker compose -p "$QUEUE_PROJECT" -f compose.queue.yaml down -v >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "Integration ports:"
echo "  PostgreSQL: $CI_POSTGRES_PORT"
echo "  MinIO:      $CI_MINIO_PORT"
echo "  MinIO UI:   $CI_MINIO_CONSOLE_PORT"
echo "  LocalStack: $CI_LOCALSTACK_PORT"
echo "  API:        $CI_API_PORT"

docker compose -p "$DB_PROJECT" -f compose.db.yaml up -d
docker compose -p "$STORAGE_PROJECT" -f compose.storage.yaml up -d
docker compose -p "$QUEUE_PROJECT" -f compose.queue.yaml up -d

POSTGRES_CONTAINER="$(
  docker compose -p "$DB_PROJECT" -f compose.db.yaml ps -q postgres
)"

if [ -z "$POSTGRES_CONTAINER" ]; then
  echo "PostgreSQL container was not created." >&2
  exit 1
fi

postgres_ready=false
for _ in $(seq 1 60); do
  if docker exec "$POSTGRES_CONTAINER" pg_isready -U ciis -d ciis >/dev/null 2>&1; then
    postgres_ready=true
    break
  fi
  sleep 2
done

if [ "$postgres_ready" != true ]; then
  echo "PostgreSQL did not become ready within 120 seconds." >&2
  docker logs "$POSTGRES_CONTAINER" >&2 || true
  exit 1
fi

minio_ready=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$CI_MINIO_PORT/minio/health/live" >/dev/null 2>&1; then
    minio_ready=true
    break
  fi
  sleep 2
done

if [ "$minio_ready" != true ]; then
  echo "MinIO did not become ready." >&2
  exit 1
fi

export AWS_ACCESS_KEY_ID='test'
export AWS_SECRET_ACCESS_KEY='test'
export AWS_DEFAULT_REGION='us-east-1'

storage_ready=false
for _ in $(seq 1 60); do
  if aws --endpoint-url "http://127.0.0.1:$CI_MINIO_PORT"       s3api head-bucket --bucket ciis-storage >/dev/null 2>&1; then
    storage_ready=true
    break
  fi
  sleep 2
done

if [ "$storage_ready" != true ]; then
  echo "MinIO bucket ciis-storage did not become ready." >&2
  exit 1
fi

localstack_ready=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$CI_LOCALSTACK_PORT/_localstack/health" >/dev/null 2>&1; then
    localstack_ready=true
    break
  fi
  sleep 2
done

if [ "$localstack_ready" != true ]; then
  echo "LocalStack did not become ready." >&2
  exit 1
fi

queue_ready=false
for _ in $(seq 1 60); do
  if aws --endpoint-url "http://127.0.0.1:$CI_LOCALSTACK_PORT"       sqs get-queue-url --queue-name ciis-analysis >/dev/null 2>&1; then
    queue_ready=true
    break
  fi
  sleep 2
done

if [ "$queue_ready" != true ]; then
  echo "LocalStack queue ciis-analysis did not become ready." >&2
  exit 1
fi

DATABASE_URL="postgresql+psycopg://ciis:ciis@127.0.0.1:$CI_POSTGRES_PORT/ciis"
STORAGE_ENDPOINT_URL="http://127.0.0.1:$CI_MINIO_PORT"
SQS_ENDPOINT_URL="http://127.0.0.1:$CI_LOCALSTACK_PORT"
API_CONTAINER="ciis-ci-api-$RUN_ID"

docker run --rm   --network host   -e "DATABASE_URL=$DATABASE_URL"   "$BACKEND_IMAGE"   python -m alembic upgrade head

docker run -d   --name "$API_CONTAINER"   --network host   -e "DATABASE_URL=$DATABASE_URL"   -e "STORAGE_ENDPOINT_URL=$STORAGE_ENDPOINT_URL"   -e STORAGE_ACCESS_KEY='ciisadmin'   -e STORAGE_SECRET_KEY='ciisadmin123'   -e STORAGE_BUCKET='ciis-storage'   -e "SQS_ENDPOINT_URL=$SQS_ENDPOINT_URL"   -e SQS_REGION='us-east-1'   -e SQS_ACCESS_KEY='test'   -e SQS_SECRET_KEY='test'   -e SQS_ANALYSIS_QUEUE_NAME='ciis-analysis'   -e SQS_ANALYSIS_DLQ_NAME='ciis-analysis-dlq'   -e CIIS_ROLE='api'   "$BACKEND_IMAGE"   python -m uvicorn app.main:app --host 0.0.0.0 --port "$CI_API_PORT" >/dev/null

api_live=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$CI_API_PORT/health/live" >/dev/null 2>&1; then
    api_live=true
    break
  fi
  sleep 2
done

if [ "$api_live" != true ]; then
  docker logs "$API_CONTAINER" >&2 || true
  echo "API liveness check failed." >&2
  exit 1
fi

curl -fsS "http://127.0.0.1:$CI_API_PORT/health/live" >/dev/null
curl -fsS "http://127.0.0.1:$CI_API_PORT/health/ready" >/dev/null

set +e
timeout 20s docker run --rm   --network host   -e "DATABASE_URL=$DATABASE_URL"   -e "STORAGE_ENDPOINT_URL=$STORAGE_ENDPOINT_URL"   -e STORAGE_ACCESS_KEY='ciisadmin'   -e STORAGE_SECRET_KEY='ciisadmin123'   -e STORAGE_BUCKET='ciis-storage'   -e "SQS_ENDPOINT_URL=$SQS_ENDPOINT_URL"   -e SQS_REGION='us-east-1'   -e SQS_ACCESS_KEY='test'   -e SQS_SECRET_KEY='test'   -e SQS_ANALYSIS_QUEUE_NAME='ciis-analysis'   -e SQS_ANALYSIS_DLQ_NAME='ciis-analysis-dlq'   -e WORKER_POLL_SECONDS='1'   -e CIIS_ROLE='worker'   "$BACKEND_IMAGE"   python -m app.workers.analysis_worker
worker_exit_code=$?
set -e

if [ "$worker_exit_code" -ne 124 ]; then
  echo "Worker smoke test failed with exit code $worker_exit_code." >&2
  exit "$worker_exit_code"
fi

echo "Container integration checks passed."
