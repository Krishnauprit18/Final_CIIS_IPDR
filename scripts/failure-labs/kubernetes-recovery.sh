#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${RUN_DESTRUCTIVE_LAB:-}" != "1" ]]; then
  echo "Refusing to inject a Kubernetes failure. Set RUN_DESTRUCTIVE_LAB=1 explicitly." >&2
  exit 2
fi

NAMESPACE="${K8S_NAMESPACE:-default}"
TIMEOUT="${K8S_TIMEOUT:-300s}"
LAB="${1:-}"

case "$LAB" in
  kill-api)
    pod="$(kubectl get pods -n "$NAMESPACE" -l app=ciis-api -o jsonpath='{.items[0].metadata.name}')"
    test -n "$pod"
    kubectl delete pod "$pod" -n "$NAMESPACE"
    kubectl rollout status deployment/ciis-api -n "$NAMESPACE" --timeout="$TIMEOUT"
    ;;
  kill-worker)
    pod="$(kubectl get pods -n "$NAMESPACE" -l app=ciis-worker -o jsonpath='{.items[0].metadata.name}')"
    test -n "$pod"
    kubectl delete pod "$pod" -n "$NAMESPACE"
    kubectl rollout status deployment/ciis-worker -n "$NAMESPACE" --timeout="$TIMEOUT"
    ;;
  db-outage)
    restore() {
      kubectl scale deployment/ciis-postgres -n "$NAMESPACE" --replicas=1 >/dev/null 2>&1 || true
    }
    trap restore EXIT
    kubectl scale deployment/ciis-postgres -n "$NAMESPACE" --replicas=0
    sleep 10
    curl --fail --silent --show-error "${API_HEALTH_URL:-http://127.0.0.1:8000/health/live}" >/dev/null
    if curl --fail --silent --show-error "${API_READY_URL:-http://127.0.0.1:8000/health/ready}" >/dev/null; then
      echo "Readiness unexpectedly stayed healthy during the database outage" >&2
      exit 1
    fi
    kubectl scale deployment/ciis-postgres -n "$NAMESPACE" --replicas=1
    kubectl rollout status deployment/ciis-postgres -n "$NAMESPACE" --timeout="$TIMEOUT"
    ;;
  *)
    echo "Usage: RUN_DESTRUCTIVE_LAB=1 $0 {kill-api|kill-worker|db-outage}" >&2
    exit 64
    ;;
esac
