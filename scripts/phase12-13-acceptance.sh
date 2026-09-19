#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATASET="${CIIS_ACCEPTANCE_DATASET:-$ROOT/Scenario A1-ARFF/synthetic.csv}"
API_PORT="${CIIS_ACCEPTANCE_API_PORT:-18008}"
PF_LOG="${TMPDIR:-/tmp}/ciis-phase13-port-forward.log"

source scripts/phase13-kube-env.sh

for d in ciis-postgres ciis-api ciis-worker ciis-web; do
  kubectl rollout status "deployment/$d" --timeout=90s
done

ORIGINAL_REPLICAS="$(kubectl get deploy ciis-worker -o jsonpath='{.spec.replicas}')"
ORIGINAL_VISIBILITY="$(kubectl get deploy ciis-worker -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="WORKER_VISIBILITY_TIMEOUT")].value}')"

cleanup() {
  set +e
  kill "${PF_PID:-0}" >/dev/null 2>&1 || true
  kubectl scale deploy ciis-worker --replicas="$ORIGINAL_REPLICAS" >/dev/null 2>&1 || true
  if [ -n "$ORIGINAL_VISIBILITY" ]; then
    kubectl set env deploy/ciis-worker WORKER_VISIBILITY_TIMEOUT="$ORIGINAL_VISIBILITY" >/dev/null 2>&1 || true
  else
    kubectl set env deploy/ciis-worker WORKER_VISIBILITY_TIMEOUT- >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

kubectl port-forward svc/api "$API_PORT:8000" >"$PF_LOG" 2>&1 &
PF_PID=$!
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:$API_PORT/" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:$API_PORT/" >/dev/null

create_case() {
  kubectl exec deployment/ciis-postgres -- psql -U ciis -d ciis -Atc \
    "INSERT INTO cases (name, created_by, created_at) VALUES ('phase13-acceptance-$(date +%s%N)', 'phase13-acceptance', NOW()) RETURNING id;" \
    | head -n1 | tr -d '[:space:]'
}

submit_job() {
  local case_id="$1"
  curl -fsS -X POST "http://127.0.0.1:$API_PORT/cases/$case_id/analysis" \
    -F "dataset_file=@$DATASET" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
}

job_json() { curl -fsS "http://127.0.0.1:$API_PORT/jobs/$1"; }
job_status() { job_json "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])'; }

wait_success() {
  local job="$1" timeout="$2" start="$(date +%s)"
  while true; do
    local status="$(job_status "$job")"
    echo "job=$job status=$status"
    [ "$status" = "SUCCEEDED" ] && return 0
    [ "$status" = "FAILED" ] && { job_json "$job"; return 1; }
    [ $(( $(date +%s) - start )) -ge "$timeout" ] && { echo "timeout waiting for $job"; return 1; }
    sleep 2
  done
}

echo "=== STEP 19: end-to-end distributed analysis ==="
CASE19="$(create_case)"
JOB19="$(submit_job "$CASE19")"
wait_success "$JOB19" 300
J19="$(job_json "$JOB19")"
echo "$J19"
RESULT_URI="$(printf '%s' "$J19" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("result_uri") or d.get("payload",{}).get("result_uri") or "")')"
[ -n "$RESULT_URI" ]
BUCKET="$(printf '%s' "$RESULT_URI" | sed -E 's#^s3://([^/]+)/.*#\1#')"
KEY="$(printf '%s' "$RESULT_URI" | sed -E 's#^s3://[^/]+/##')"
bash scripts/floci-aws.sh s3api head-object --bucket "$BUCKET" --key "$KEY" >/dev/null
bash scripts/floci-aws.sh s3 ls s3://ciis-raw-files/analysis-inputs/ --recursive | grep -q .
echo "STEP 19 PASS"

echo "=== STEP 20: independently scalable workers ==="
kubectl scale deploy ciis-worker --replicas=2 >/dev/null
kubectl rollout status deploy/ciis-worker --timeout=120s
[ "$(kubectl get pods -l app=ciis-worker --field-selector=status.phase=Running --no-headers | wc -l)" -ge 2 ]
CASE20="$(create_case)"
J20A="$(submit_job "$CASE20")"
J20B="$(submit_job "$CASE20")"
wait_success "$J20A" 300
wait_success "$J20B" 300
kubectl get pods -l app=ciis-worker -o wide
echo "STEP 20 PASS"

echo "=== STEP 21: worker crash/recovery ==="
kubectl scale deploy ciis-worker --replicas=1 >/dev/null
kubectl set env deploy/ciis-worker WORKER_VISIBILITY_TIMEOUT=15 >/dev/null
kubectl rollout status deploy/ciis-worker --timeout=120s
CASE21="$(create_case)"
JOB21="$(submit_job "$CASE21")"
START="$(date +%s)"
while true; do
  STATUS="$(job_status "$JOB21")"
  [ "$STATUS" = "RUNNING" ] && break
  if [ "$STATUS" = "SUCCEEDED" ]; then
    echo "INCONCLUSIVE: dataset finished before worker could be killed."
    echo "Rerun with CIIS_ACCEPTANCE_DATASET=/path/to/larger.csv"
    exit 2
  fi
  [ "$STATUS" = "FAILED" ] && exit 1
  [ $(( $(date +%s) - START )) -ge 60 ] && exit 1
  sleep 1
done
OLD_WORKER="$(kubectl get pods -l app=ciis-worker -o jsonpath='{.items[0].metadata.name}')"
kubectl delete pod "$OLD_WORKER" --wait=false >/dev/null
for _ in $(seq 1 60); do
  NEW_WORKER="$(kubectl get pods -l app=ciis-worker -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  READY="$(kubectl get pods -l app=ciis-worker -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null || true)"
  [ -n "$NEW_WORKER" ] && [ "$NEW_WORKER" != "$OLD_WORKER" ] && [ "$READY" = "true" ] && break
  sleep 1
done
[ "$NEW_WORKER" != "$OLD_WORKER" ]
wait_success "$JOB21" 180
echo "STEP 21 PASS"

echo "=== STEP 22: immutable Git-SHA ECR tags ==="
GIT_SHA="$(git rev-parse --short HEAD)"
REGISTRY="000000000000.dkr.ecr.us-east-1.localhost:4566"
ORIGINAL_DIGEST="$(bash scripts/floci-aws.sh ecr describe-images --repository-name ciis-api --image-ids "imageTag=$GIT_SHA" --query 'imageDetails[0].imageDigest' --output text)"
[ -n "$ORIGINAL_DIGEST" ] && [ "$ORIGINAL_DIGEST" != "None" ]
bash scripts/floci-aws.sh ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
docker image inspect "ciis-web:$GIT_SHA" >/dev/null
docker tag "ciis-web:$GIT_SHA" "$REGISTRY/ciis-api:$GIT_SHA"
set +e
docker push "$REGISTRY/ciis-api:$GIT_SHA" >/tmp/ciis-ecr-immutable.log 2>&1
RC=$?
set -e
cat /tmp/ciis-ecr-immutable.log
[ "$RC" -ne 0 ]
AFTER_DIGEST="$(bash scripts/floci-aws.sh ecr describe-images --repository-name ciis-api --image-ids "imageTag=$GIT_SHA" --query 'imageDetails[0].imageDigest' --output text)"
[ "$ORIGINAL_DIGEST" = "$AFTER_DIGEST" ]
echo "STEP 22 PASS"

echo "PHASE 12/13 ACCEPTANCE PASSED"
