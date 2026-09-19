#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/8] Verifying Kubernetes authentication"
source scripts/phase13-kube-env.sh
kubectl auth can-i get pods >/dev/null
kubectl get nodes

echo "[2/8] Verifying workloads"
kubectl get deployments
for deployment in ciis-postgres ciis-api ciis-worker ciis-web; do
  kubectl rollout status "deployment/$deployment" --timeout=60s
done

echo "[3/8] Verifying services and Floci bridge"
kubectl get svc api ciis-web floci-local
kubectl get endpoints floci-local

echo "[4/8] Verifying API from inside the cluster"
kubectl run ciis-api-smoke --rm -i --restart=Never \
  --image=curlimages/curl:8.10.1 \
  --command -- curl -fsS http://api:8000/ >/dev/null

echo "[5/8] Verifying frontend from inside the cluster"
kubectl run ciis-web-smoke --rm -i --restart=Never \
  --image=curlimages/curl:8.10.1 \
  --command -- curl -fsS http://ciis-web:8080/healthz

echo "[6/8] Verifying Floci S3"
scripts/floci-aws.sh s3api head-bucket --bucket ciis-raw-files
scripts/floci-aws.sh s3api head-bucket --bucket ciis-results

echo "[7/8] Verifying Floci SQS + DLQ"
QUEUE_URL="$(scripts/floci-aws.sh sqs get-queue-url --queue-name ciis-analysis-jobs --query QueueUrl --output text)"
scripts/floci-aws.sh sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names RedrivePolicy QueueArn

echo "[8/8] Verifying worker can reach queue"
worker_logs="$(kubectl logs deployment/ciis-worker --tail=100)"
printf '%s\n' "$worker_logs"
if printf '%s\n' "$worker_logs" | grep -q "queue error"; then
  echo "Worker reports queue connectivity errors." >&2
  exit 1
fi

echo
echo "Phase 12/13 infrastructure smoke verification passed."
echo "For host access run, in separate terminals:"
echo "  source scripts/phase13-kube-env.sh && kubectl port-forward svc/ciis-web 8088:8080"
echo "  source scripts/phase13-kube-env.sh && kubectl port-forward svc/api 8008:8000"
