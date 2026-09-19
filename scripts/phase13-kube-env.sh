#!/usr/bin/env bash
# Source this file to configure AWS + kubectl authentication for the local
# Floci EKS cluster:
#   source scripts/phase13-kube-env.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform/environments/local"

export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="$(terraform -chdir="$TF_DIR" output -raw kube_admin_access_key_id)"
export AWS_SECRET_ACCESS_KEY="$(terraform -chdir="$TF_DIR" output -raw kube_admin_secret_access_key)"

aws eks update-kubeconfig --name ciis-local >/dev/null

echo "Configured Floci EKS shell environment for ciis-local."
