#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/backend"
: "${DATABASE_URL:?DATABASE_URL is required}"

python -m alembic current
head="$(python -m alembic heads | awk 'NF {print $1; exit}')"
current="$(python -m alembic current | awk 'NF {print $1; exit}')"
test -n "$head" -a -n "$current"
test "$head" = "$current"
echo "Migration head is current: $head"
echo "Rollback strategy is documented; no downgrade was executed against the configured database."
