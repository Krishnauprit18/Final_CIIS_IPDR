#!/usr/bin/env bash
set -Eeuo pipefail

: "${BACKUP_FILE:?BACKUP_FILE must point to a custom-format pg_dump file}"
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL must point to a disposable restore target}"
CLI_RESTORE_DATABASE_URL="${RESTORE_DATABASE_URL/postgresql+psycopg:/postgresql:}"

test -s "$BACKUP_FILE"
if [[ "${ALLOW_RESTORE_TARGET:-}" != "1" ]]; then
  echo "Refusing restore. Set ALLOW_RESTORE_TARGET=1 only for a disposable target database." >&2
  exit 2
fi

if command -v pg_restore >/dev/null 2>&1; then
  pg_restore \
    --clean \
    --if-exists \
    --no-owner \
    --dbname "$CLI_RESTORE_DATABASE_URL" \
    "$BACKUP_FILE"
else
  backup_dir="$(cd "$(dirname "$BACKUP_FILE")" && pwd)"
  backup_name="$(basename "$BACKUP_FILE")"
  docker run --rm --network host \
    -v "$backup_dir:/backup" \
    postgres:16-alpine \
    pg_restore --clean --if-exists --no-owner \
      --dbname "$CLI_RESTORE_DATABASE_URL" "/backup/$backup_name"
fi

if command -v psql >/dev/null 2>&1; then
  revision="$(psql "$CLI_RESTORE_DATABASE_URL" -Atqc 'SELECT version_num FROM alembic_version')"
else
  revision="$(docker run --rm --network host postgres:16-alpine \
    psql "$CLI_RESTORE_DATABASE_URL" -Atqc 'SELECT version_num FROM alembic_version')"
fi
test -n "$revision"
echo "Restore drill PASS; restored Alembic revision: $revision"
