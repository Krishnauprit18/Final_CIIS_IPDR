#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for cmd in aws docker kubectl helm; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
done

export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"

REGISTRY="000000000000.dkr.ecr.us-east-1.localhost:4566"
GIT_SHA="$(git rev-parse --short HEAD)"

echo "Deploying Git SHA: $GIT_SHA"

echo "[1/6] Logging in to Floci ECR"
aws ecr get-login-password   | docker login --username AWS --password-stdin "$REGISTRY"

echo "[2/6] Building images"
docker build -t "ciis-backend:$GIT_SHA" ./backend
docker build   --build-arg REACT_APP_API_BASE_URL=/api   -t "ciis-web:$GIT_SHA"   ./frontend

push_if_missing() {
  local repo_name="$1"
  local source_image="$2"
  local target="$REGISTRY/$repo_name:$GIT_SHA"

  if aws ecr describe-images       --repository-name "$repo_name"       --image-ids "imageTag=$GIT_SHA" >/dev/null 2>&1; then
    echo "$target already exists; immutable tag preserved."
    return
  fi

  docker tag "$source_image" "$target"
  docker push "$target"
}

echo "[3/6] Pushing immutable Git-SHA images"
push_if_missing ciis-api "ciis-backend:$GIT_SHA"
push_if_missing ciis-worker "ciis-backend:$GIT_SHA"
push_if_missing ciis-web "ciis-web:$GIT_SHA"

echo "[4/6] Checking Kubernetes cluster"
kubectl get nodes

echo "[5/6] Linting and installing Helm chart"
helm lint deploy/helm/ciis
helm upgrade --install ciis deploy/helm/ciis   --set "image.tag=$GIT_SHA"

echo "[6/6] Waiting for workloads"
kubectl rollout status deployment/ciis-postgres --timeout=180s
kubectl rollout status deployment/ciis-api --timeout=300s
kubectl rollout status deployment/ciis-worker --timeout=300s
kubectl rollout status deployment/ciis-web --timeout=180s

echo
kubectl get deployments
echo
kubectl get pods
echo
kubectl get services
echo
echo "Phase 12/13 deployment complete."
echo "Frontend: kubectl port-forward svc/ciis-web 8088:8080"
echo "API:      kubectl port-forward svc/api 8008:8000"
