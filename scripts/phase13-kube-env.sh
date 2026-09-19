#!/usr/bin/env bash
# Source this file to configure AWS + kubectl authentication for the local
# Floci EKS cluster:
#   source scripts/phase13-kube-env.sh
#
# This script also pins the dedicated kube-admin credentials into the kubeconfig
# exec entry. That keeps kubectl working even if the interactive shell later
# exports test/test credentials for ordinary Floci S3/SQS inspection.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform/environments/local"

export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"

KUBE_AWS_ACCESS_KEY_ID="$(terraform -chdir="$TF_DIR" output -raw kube_admin_access_key_id)"
KUBE_AWS_SECRET_ACCESS_KEY="$(terraform -chdir="$TF_DIR" output -raw kube_admin_secret_access_key)"

# Use the dedicated principal while creating/updating the kubeconfig entry.
export AWS_ACCESS_KEY_ID="$KUBE_AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$KUBE_AWS_SECRET_ACCESS_KEY"

aws eks update-kubeconfig --name ciis-local >/dev/null

KUBE_USER="$(kubectl config view --minify -o jsonpath='{.contexts[0].context.user}')"
if [ -z "$KUBE_USER" ]; then
  echo "Unable to determine kubeconfig user for ciis-local." >&2
  return 1 2>/dev/null || exit 1
fi

# aws eks update-kubeconfig creates an exec-based user. Pin credentials on that
# exec stanza so subsequent shell-level AWS credential changes cannot silently
# invalidate kubectl authentication.
kubectl config set-credentials "$KUBE_USER" \
  --exec-env="AWS_ENDPOINT_URL=http://localhost:4566" \
  --exec-env="AWS_DEFAULT_REGION=us-east-1" \
  --exec-env="AWS_REGION=us-east-1" \
  --exec-env="AWS_ACCESS_KEY_ID=$KUBE_AWS_ACCESS_KEY_ID" \
  --exec-env="AWS_SECRET_ACCESS_KEY=$KUBE_AWS_SECRET_ACCESS_KEY" >/dev/null

echo "Configured Floci EKS shell environment for ciis-local."
echo "kubectl authentication is pinned to the dedicated ciis-kube-admin credentials."
