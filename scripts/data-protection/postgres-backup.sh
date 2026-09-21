#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?DATABASE_URL must point to the source PostgreSQL database}"
CLI_DATABASE_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
BACKUP_DIR="${BACKUP_DIR:-.ci-artifacts/backups}"
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$BACKUP_DIR/ciis-${timestamp}.dump"

if command -v pg_dump >/dev/null 2>&1; then
  pg_dump --format=custom --no-owner --file "$backup_file" "$CLI_DATABASE_URL"
else
  backup_dir="$(cd "$(dirname "$backup_file")" && pwd)"
  backup_name="$(basename "$backup_file")"
  docker run --rm --network host \
    -v "$backup_dir:/backup" \
    postgres:16-alpine \
    pg_dump --format=custom --no-owner --file "/backup/$backup_name" "$CLI_DATABASE_URL"
fi
test -s "$backup_file"
sha256sum "$backup_file" | tee "${backup_file}.sha256"
echo "Created PostgreSQL backup: $backup_file"
