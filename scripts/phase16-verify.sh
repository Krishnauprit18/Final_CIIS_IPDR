#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source scripts/phase13-kube-env.sh

echo "[1/6] API metrics"
API_POD="$(kubectl get pods -l app=ciis-api -o jsonpath='{.items[0].metadata.name}')"
kubectl exec "$API_POD" -- python - <<'PY'
from prometheus_client import generate_latest
payload = generate_latest().decode()
required = [
    "ciis_http_requests_total",
    "ciis_http_request_duration_seconds",
    "ciis_sqs_queue_depth",
    "ciis_db_pool_checked_out",
]
for name in required:
    assert name in payload, name
print("API metrics: OK")
PY

echo "[2/6] Worker metrics service"
kubectl get svc ciis-worker-metrics >/dev/null
WORKER_POD="$(kubectl get pods -l app=ciis-worker -o jsonpath='{.items[0].metadata.name}')"
kubectl exec "$WORKER_POD" -- python - <<'PY'
import urllib.request
payload = urllib.request.urlopen("http://127.0.0.1:9101/metrics", timeout=5).read().decode()
assert "ciis_analysis_jobs_total" in payload
assert "ciis_active_workers" in payload
print("Worker metrics: OK")
PY

echo "[3/6] Correlation log fields"
kubectl logs "$WORKER_POD" --tail=100 | grep -Eq '"service":"worker"|"service":"ciis-worker"'

echo "[4/6] Prometheus config"
grep -q 'api:8000' observability/prometheus/prometheus.yml
grep -q 'worker:9101' observability/prometheus/prometheus.yml

echo "[5/6] Grafana dashboard and OTEL collector"
test -f observability/grafana/dashboards/ciis-overview.json
test -f observability/otel/collector-config.yaml

echo "[6/6] Backend tests"
(
  cd backend
  python -m pytest -q
)

echo "PHASE 16 ACCEPTANCE PASSED"
