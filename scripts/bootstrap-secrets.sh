#!/usr/bin/env bash
set -euo pipefail

: "${CIIS_DATABASE_URL:?CIIS_DATABASE_URL is required}"
: "${CIIS_POSTGRES_PASSWORD:?CIIS_POSTGRES_PASSWORD is required}"
: "${CIIS_AUTH_SECRET:?CIIS_AUTH_SECRET is required}"

DATABASE_SECRET="$(python3 - <<'PY'
import json
import os

print(json.dumps({
    "DATABASE_URL": os.environ["CIIS_DATABASE_URL"],
    "POSTGRES_PASSWORD": os.environ["CIIS_POSTGRES_PASSWORD"],
}))
PY
)"

APPLICATION_SECRET="$(python3 - <<'PY'
import json
import os

print(json.dumps({
    "AUTH_SECRET": os.environ["CIIS_AUTH_SECRET"],
}))
PY
)"

bash scripts/floci-aws.sh secretsmanager put-secret-value \
  --secret-id ciis/database \
  --secret-string "$DATABASE_SECRET" >/dev/null

bash scripts/floci-aws.sh secretsmanager put-secret-value \
  --secret-id ciis/application \
  --secret-string "$APPLICATION_SECRET" >/dev/null

echo "CIIS Secrets Manager values updated successfully."
