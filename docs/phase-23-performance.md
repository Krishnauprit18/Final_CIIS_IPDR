# Phase 23 — Performance and load testing

The repository now contains an explicit Locust harness; it does not invent
throughput or latency numbers. Every run must save the CSV/HTML output and
record the environment, image tag, dataset size, users, spawn rate, duration,
queue depth, and resource observations.

## Workloads

- `AuthenticatedUser`: login, case reads, profile reads, and liveness.
- `AnalysisUser`: real dataset upload, asynchronous submission, and status
  polling until a terminal state.

The harness intentionally requires credentials and a dataset path through
environment variables. No secret or imaginary fixture is committed.

```bash
python -m pip install -r performance/requirements.txt
LOCUST_HOST=http://127.0.0.1:8000 \
LOCUST_USERS=2 \
LOCUST_SPAWN_RATE=1 \
LOCUST_RUN_TIME=60s \
CIIS_USERNAME='use-a-local-test-user' \
CIIS_PASSWORD='use-a-local-test-password' \
CIIS_DATASET_PATH="$PWD/Scenario A1-ARFF/synthetic.csv" \
  bash scripts/performance/run-locust.sh
```

Run read-only and analysis workloads separately. Report p50/p95/p99,
throughput, errors, queue depth, job duration, and CPU/memory observations
from the same run; do not write a resume metric until before/after evidence
exists.
