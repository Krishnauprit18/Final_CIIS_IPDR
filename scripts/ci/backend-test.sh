#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

CI_VENV="${CI_VENV:-$ROOT/.ci-venv}"
PYTHON="$CI_VENV/bin/python"
COMPOSE_PROJECT="${CI_DB_COMPOSE_PROJECT:-ciis-ci-db-${BUILD_NUMBER:-$$}}"

free_port() {
  python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

export CI_POSTGRES_PORT="${CI_POSTGRES_PORT:-$(free_port)}"

cleanup() {
  docker compose -p "$COMPOSE_PROJECT" -f compose.db.yaml down -v >/dev/null 2>&1 || true
}

trap cleanup EXIT

if [ ! -x "$PYTHON" ]; then
  python3 -m venv "$CI_VENV"
  "$PYTHON" -m pip install --upgrade pip setuptools wheel
  "$PYTHON" -m pip install -r "$ROOT/backend/requirements-dev.txt"
fi

"$PYTHON" -m pip install -r "$ROOT/backend/requirements-dev.txt" >/dev/null

echo "CI PostgreSQL host port: $CI_POSTGRES_PORT"

docker compose -p "$COMPOSE_PROJECT" -f compose.db.yaml up -d

POSTGRES_CONTAINER="$(
  docker compose -p "$COMPOSE_PROJECT" -f compose.db.yaml ps -q postgres
)"

if [ -z "$POSTGRES_CONTAINER" ]; then
  echo "PostgreSQL container was not created." >&2
  exit 1
fi

postgres_ready=false
for _ in $(seq 1 60); do
  if docker exec "$POSTGRES_CONTAINER"       pg_isready -U ciis -d ciis >/dev/null 2>&1; then
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

cd "$ROOT/backend"

mkdir -p "$ROOT/.ci-artifacts/backend"

export DATABASE_URL="postgresql+psycopg://ciis:ciis@127.0.0.1:${CI_POSTGRES_PORT}/ciis"

"$PYTHON" -m alembic upgrade head
"$PYTHON" -m alembic current
"$PYTHON" -m pytest -q \
  --junitxml="$ROOT/.ci-artifacts/backend/junit.xml" \
  --cov=app \
  --cov-report=term-missing \
  --cov-report="xml:$ROOT/.ci-artifacts/backend/coverage.xml"
