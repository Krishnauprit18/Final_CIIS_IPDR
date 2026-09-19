#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source scripts/phase13-kube-env.sh

DATABASE_SECRET="$(
  bash scripts/floci-aws.sh secretsmanager get-secret-value \
    --secret-id ciis/database \
    --query SecretString \
    --output text
)"

APPLICATION_SECRET="$(
  bash scripts/floci-aws.sh secretsmanager get-secret-value \
    --secret-id ciis/application \
    --query SecretString \
    --output text
)"

export DATABASE_SECRET APPLICATION_SECRET

DATABASE_URL="$(
python3 - <<'PY'
import json
import os
print(json.loads(os.environ["DATABASE_SECRET"])["DATABASE_URL"])
PY
)"

POSTGRES_PASSWORD="$(
python3 - <<'PY'
import json
import os
print(json.loads(os.environ["DATABASE_SECRET"])["POSTGRES_PASSWORD"])
PY
)"

AUTH_SECRET="$(
python3 - <<'PY'
import json
import os
print(json.loads(os.environ["APPLICATION_SECRET"])["AUTH_SECRET"])
PY
)"

kubectl create secret generic ciis-runtime-secrets \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=AUTH_SECRET="$AUTH_SECRET" \
  --dry-run=client \
  -o yaml | kubectl apply -f -

echo "Kubernetes Secret ciis-runtime-secrets synchronized."
