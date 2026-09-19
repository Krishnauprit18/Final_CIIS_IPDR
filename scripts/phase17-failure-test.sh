#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source scripts/phase13-kube-env.sh

API_PORT="${CIIS_HEALTH_TEST_PORT:-18008}"
PF_LOG="${TMPDIR:-/tmp}/ciis-phase17-port-forward.log"
PF_PID=""

cleanup() {
  set +e
  kubectl scale deployment ciis-postgres --replicas=1 >/dev/null 2>&1 || true
  if [ -n "$PF_PID" ]; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

kubectl rollout status deployment/ciis-api --timeout=120s
kubectl rollout status deployment/ciis-postgres --timeout=120s

kubectl port-forward svc/api "$API_PORT:8000" >"$PF_LOG" 2>&1 &
PF_PID=$!

for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:$API_PORT/health/live" >/dev/null 2>&1 && break
  sleep 1
done

echo "[1/6] Healthy liveness"
curl -fsS "http://127.0.0.1:$API_PORT/health/live"
echo

echo "[2/6] Healthy readiness"
curl -fsS "http://127.0.0.1:$API_PORT/health/ready"
echo

echo "[3/6] Stop PostgreSQL"
kubectl scale deployment ciis-postgres --replicas=0 >/dev/null
kubectl wait --for=delete pod -l app=ciis-postgres --timeout=120s || true

echo "[4/6] Liveness must stay 200"
LIVE_CODE="$(curl -sS -o /tmp/ciis-live.json -w '%{http_code}' "http://127.0.0.1:$API_PORT/health/live")"
cat /tmp/ciis-live.json
echo
if [ "$LIVE_CODE" != "200" ]; then
  echo "Expected liveness 200, got $LIVE_CODE" >&2
  exit 1
fi

echo "[5/6] Readiness must become 503"
READY_CODE=""
for _ in $(seq 1 30); do
  READY_CODE="$(curl -sS -o /tmp/ciis-ready.json -w '%{http_code}' "http://127.0.0.1:$API_PORT/health/ready" || true)"
  if [ "$READY_CODE" = "503" ]; then
    break
  fi
  sleep 2
done
cat /tmp/ciis-ready.json
echo
if [ "$READY_CODE" != "503" ]; then
  echo "Expected readiness 503, got $READY_CODE" >&2
  exit 1
fi

echo "[6/6] Restore PostgreSQL and wait for readiness recovery"
kubectl scale deployment ciis-postgres --replicas=1 >/dev/null
kubectl rollout status deployment/ciis-postgres --timeout=180s

for _ in $(seq 1 60); do
  READY_CODE="$(curl -sS -o /tmp/ciis-ready-recovered.json -w '%{http_code}' "http://127.0.0.1:$API_PORT/health/ready" || true)"
  if [ "$READY_CODE" = "200" ]; then
    cat /tmp/ciis-ready-recovered.json
    echo
    echo "PHASE 17 DATABASE FAILURE LAB PASSED"
    exit 0
  fi
  sleep 2
done

echo "Readiness did not recover after PostgreSQL restart" >&2
exit 1
