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
  if aws s3api list-buckets >/dev/null 2>&1; then
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

state_has() {
  terraform state show "$1" >/dev/null 2>&1
}

import_if_missing() {
  local address="$1"
  local id="$2"
  if state_has "$address"; then
    echo "Terraform already manages $address"
    return
  fi
  echo "Importing $address"
  terraform import "$address" "$id"
}

echo "[5/7] Reconciling resources created by earlier partial applies"

if aws s3api head-bucket --bucket ciis-raw-files >/dev/null 2>&1 && ! state_has module.s3.aws_s3_bucket.raw; then
  import_if_missing module.s3.aws_s3_bucket.raw ciis-raw-files
fi

if aws s3api head-bucket --bucket ciis-results >/dev/null 2>&1 && ! state_has module.s3.aws_s3_bucket.results; then
  import_if_missing module.s3.aws_s3_bucket.results ciis-results
fi

if aws iam get-role --role-name ciis-app-role >/dev/null 2>&1 && ! state_has module.iam.aws_iam_role.ciis_app; then
  import_if_missing module.iam.aws_iam_role.ciis_app ciis-app-role
fi

if aws iam get-role --role-name ciis-eks-cluster-role >/dev/null 2>&1 && ! state_has module.iam.aws_iam_role.eks_cluster; then
  import_if_missing module.iam.aws_iam_role.eks_cluster ciis-eks-cluster-role
fi

for pair in   "module.ecr.aws_ecr_repository.api:ciis-api"   "module.ecr.aws_ecr_repository.worker:ciis-worker"   "module.ecr.aws_ecr_repository.web:ciis-web"; do
  address="${pair%%:*}"
  repo_name="${pair#*:}"
  if aws ecr describe-repositories --repository-names "$repo_name" >/dev/null 2>&1 && ! state_has "$address"; then
    import_if_missing "$address" "$repo_name"
  fi
done

if ! state_has module.sqs.aws_sqs_queue.dlq; then
  dlq_url="$(aws sqs get-queue-url --queue-name ciis-analysis-dlq --query QueueUrl --output text 2>/dev/null || true)"
  if [ -n "$dlq_url" ] && [ "$dlq_url" != "None" ]; then
    import_if_missing module.sqs.aws_sqs_queue.dlq "$dlq_url"
  fi
fi

if ! state_has module.sqs.aws_sqs_queue.jobs; then
  jobs_url="$(aws sqs get-queue-url --queue-name ciis-analysis-jobs --query QueueUrl --output text 2>/dev/null || true)"
  if [ -n "$jobs_url" ] && [ "$jobs_url" != "None" ]; then
    import_if_missing module.sqs.aws_sqs_queue.jobs "$jobs_url"
  fi
fi

if aws eks describe-cluster --name ciis-local >/dev/null 2>&1 && ! state_has module.eks.aws_eks_cluster.ciis; then
  import_if_missing module.eks.aws_eks_cluster.ciis ciis-local
fi

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
