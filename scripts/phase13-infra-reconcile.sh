#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform/environments/local"

export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"

echo "[1/7] Starting Floci"
cd "$ROOT"
docker compose -f compose.floci.yaml up -d --force-recreate

echo "[2/7] Waiting for Floci"
for _ in $(seq 1 30); do
  if aws sts get-caller-identity >/dev/null 2>&1 || aws s3api list-buckets >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[3/7] Ensuring remote-state bucket exists"
if ! aws s3api head-bucket --bucket ciis-terraform-state >/dev/null 2>&1; then
  aws s3api create-bucket --bucket ciis-terraform-state >/dev/null
fi

echo "[4/7] Initializing Terraform"
cd "$TF_DIR"
terraform init -reconfigure

import_ecr_if_needed() {
  local address="$1"
  local repo_name="$2"

  if terraform state show "$address" >/dev/null 2>&1; then
    echo "Terraform already manages $repo_name"
    return
  fi

  if aws ecr describe-repositories --repository-names "$repo_name" >/dev/null 2>&1; then
    echo "Importing existing ECR repository $repo_name"
    terraform import "$address" "$repo_name"
  fi
}

echo "[5/7] Reconciling pre-existing ECR repositories"
import_ecr_if_needed module.ecr.aws_ecr_repository.api ciis-api
import_ecr_if_needed module.ecr.aws_ecr_repository.worker ciis-worker
import_ecr_if_needed module.ecr.aws_ecr_repository.web ciis-web

echo "[6/7] Applying Terraform"
terraform fmt -recursive
terraform validate
terraform apply -auto-approve

echo "[7/7] Waiting for EKS cluster to become ACTIVE"
for _ in $(seq 1 60); do
  status="$(aws eks describe-cluster --name ciis-local --query 'cluster.status' --output text 2>/dev/null || true)"
  echo "EKS status: ${status:-not-ready}"
  if [ "$status" = "ACTIVE" ]; then
    break
  fi
  sleep 5
done

status="$(aws eks describe-cluster --name ciis-local --query 'cluster.status' --output text)"
if [ "$status" != "ACTIVE" ]; then
  echo "EKS did not become ACTIVE."
  exit 1
fi

aws eks update-kubeconfig --name ciis-local >/dev/null

echo
echo "Infrastructure ready."
terraform state list
echo
aws ecr describe-repositories --query 'repositories[].repositoryName'
echo
aws eks describe-cluster --name ciis-local --query 'cluster.{name:name,status:status,endpoint:endpoint}'
echo
if command -v kubectl >/dev/null 2>&1; then
  kubectl get nodes
else
  echo "kubectl is not installed; install it before running the deploy script."
fi
