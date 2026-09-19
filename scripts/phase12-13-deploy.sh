#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform/environments/local"
cd "$ROOT"

for cmd in aws docker kubectl helm terraform; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
done

diagnose_kubernetes() {
  echo
  echo "=== Phase 12/13 Kubernetes diagnostics ==="
  kubectl get nodes -o wide || true
  echo
  kubectl get pods -o wide || true
  echo
  kubectl get events --sort-by=.lastTimestamp | tail -n 80 || true
  echo
  kubectl describe deployment ciis-api || true
  echo
  for pod in $(kubectl get pods -l app=ciis-api -o name 2>/dev/null); do
    echo "--- $pod init-container logs ---"
    kubectl logs "$pod" -c migrate --tail=120 || true
    echo "--- $pod api logs ---"
    kubectl logs "$pod" -c api --tail=120 || true
    echo "--- $pod previous api logs ---"
    kubectl logs "$pod" -c api --previous --tail=120 || true
  done
}
trap diagnose_kubernetes ERR

export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"

# Use the dedicated IAM principal created by Terraform. Floci EKS deliberately
# rejects test/test for Kubernetes authentication.
export AWS_ACCESS_KEY_ID="$(terraform -chdir="$TF_DIR" output -raw kube_admin_access_key_id)"
export AWS_SECRET_ACCESS_KEY="$(terraform -chdir="$TF_DIR" output -raw kube_admin_secret_access_key)"

REGISTRY="000000000000.dkr.ecr.us-east-1.localhost:4566"
GIT_SHA="$(git rev-parse --short HEAD)"

echo "Deploying Git SHA: $GIT_SHA"

echo "[1/6] Logging in to Floci ECR"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"

echo "[2/6] Building images"
docker build -t "ciis-backend:$GIT_SHA" ./backend
docker build \
  --build-arg REACT_APP_API_BASE_URL=/api \
  -t "ciis-web:$GIT_SHA" \
  ./frontend

push_if_missing() {
  local repo_name="$1"
  local source_image="$2"
  local target="$REGISTRY/$repo_name:$GIT_SHA"

  if aws ecr describe-images \
      --repository-name "$repo_name" \
      --image-ids "imageTag=$GIT_SHA" >/dev/null 2>&1; then
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

# Persistent Floci EKS volumes can retain an old k3s node object when the
# backing container is recreated with a new hostname. If a healthy replacement
# exists, remove stale NotReady nodes so scheduling and diagnostics are clean.
ready_count="$(kubectl get nodes --no-headers | awk '$2 ~ /^Ready/ {count++} END {print count+0}')"
if [ "$ready_count" -gt 0 ]; then
  while read -r stale_node; do
    [ -z "$stale_node" ] && continue
    echo "Removing stale NotReady node object: $stale_node"
    kubectl delete node "$stale_node" --wait=false || true
  done < <(kubectl get nodes --no-headers | awk '$2 ~ /^NotReady/ {print $1}')
fi

# Bridge the Kubernetes pod network to the Floci container using a normal
# ClusterIP Service + explicit Endpoints object. Docker/Compose service DNS
# ("floci") is not a Kubernetes DNS name and must not be assumed inside pods.
FLOCI_CONTAINER_ID="$(docker compose -f compose.floci.yaml ps -q floci)"
if [ -z "$FLOCI_CONTAINER_ID" ]; then
  echo "Floci container is not running. Run scripts/phase13-infra-reconcile.sh first."
  exit 1
fi
FLOCI_IP="$(docker inspect -f '{{(index .NetworkSettings.Networks "final_ciis_ipdr_default").IPAddress}}' "$FLOCI_CONTAINER_ID")"
if [ -z "$FLOCI_IP" ]; then
  echo "Unable to determine Floci IP on final_ciis_ipdr_default."
  exit 1
fi
echo "Floci Kubernetes bridge target: $FLOCI_IP:4566"

echo "[5/6] Synchronizing runtime secrets and installing Helm chart"
if [ -x scripts/phase14-sync-k8s-secrets.sh ]; then
  bash scripts/phase14-sync-k8s-secrets.sh
fi
helm lint deploy/helm/ciis
helm upgrade --install ciis deploy/helm/ciis \
  --set "image.tag=$GIT_SHA" \
  --set "config.flociIp=$FLOCI_IP"

echo "[6/6] Waiting for workloads"
kubectl rollout status deployment/ciis-postgres --timeout=180s
kubectl rollout status deployment/ciis-api --timeout=300s
kubectl rollout status deployment/ciis-worker --timeout=300s
kubectl rollout status deployment/ciis-web --timeout=180s

trap - ERR

echo
kubectl get deployments
echo
kubectl get pods -o wide
echo
kubectl get services
echo
echo "Phase 12/13 deployment complete."
echo "Frontend: kubectl port-forward svc/ciis-web 8088:8080"
echo "API:      kubectl port-forward svc/api 8008:8000"
