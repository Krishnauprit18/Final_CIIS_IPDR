#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

cleanup() {
  docker compose -f compose.db.yaml down >/dev/null 2>&1 || true
}

trap cleanup EXIT

docker compose -f compose.db.yaml up -d

POSTGRES_CONTAINER="$(
  docker compose -f compose.db.yaml ps -q postgres
)"

if [ -z "$POSTGRES_CONTAINER" ]; then
  echo "PostgreSQL container was not created." >&2
  exit 1
fi

for _ in $(seq 1 60); do
  if docker exec "$POSTGRES_CONTAINER" \
      pg_isready -U ciis -d ciis >/dev/null 2>&1; then
    break
  fi

  sleep 2
done

docker exec "$POSTGRES_CONTAINER" \
  pg_isready -U ciis -d ciis >/dev/null

cd backend

export DATABASE_URL='postgresql+psycopg://ciis:ciis@127.0.0.1:5432/ciis'

python -m alembic upgrade head
python -m alembic current
python -m pytest -q
