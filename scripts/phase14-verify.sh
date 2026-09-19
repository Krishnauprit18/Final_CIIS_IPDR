#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/7] Terraform formatting and validation"
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/environments/local validate

echo "[2/7] Secrets Manager resources"
bash scripts/floci-aws.sh secretsmanager describe-secret --secret-id ciis/database >/dev/null
bash scripts/floci-aws.sh secretsmanager describe-secret --secret-id ciis/application >/dev/null

echo "[3/7] IAM least-privilege policy"
POLICY="$(bash scripts/floci-aws.sh iam get-role-policy   --role-name ciis-app-role   --policy-name ciis-app-secrets-read   --query PolicyDocument   --output json)"
printf '%s' "$POLICY" | grep -q 'secretsmanager:GetSecretValue'
if printf '%s' "$POLICY" | grep -Eq '"Action"[[:space:]]*:[[:space:]]*"\*"|"Resource"[[:space:]]*:[[:space:]]*"\*"'; then
  echo "Wildcard IAM permission found in ciis-app-secrets-read" >&2
  exit 1
fi

echo "[4/7] Kubernetes runtime secret"
source scripts/phase13-kube-env.sh
kubectl get secret ciis-runtime-secrets >/dev/null

echo "[5/7] ServiceAccount and workloads"
kubectl get serviceaccount ciis-app >/dev/null
kubectl rollout status deployment/ciis-api --timeout=120s
kubectl rollout status deployment/ciis-worker --timeout=120s

echo "[6/7] Helm lint"
helm lint deploy/helm/ciis

echo "[7/7] Secret leakage checks"
if git grep -n 'ciisadmin123'; then
  echo "Legacy hardcoded storage secret still exists." >&2
  exit 1
fi
if git grep -n 'password: ciis'; then
  echo "Plaintext Helm database password still exists." >&2
  exit 1
fi

echo "PHASE 14 ACCEPTANCE PASSED"
