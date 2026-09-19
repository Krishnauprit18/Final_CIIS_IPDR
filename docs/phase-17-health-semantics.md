# Phase 17 — Health and Readiness Semantics

## API endpoints

`GET /health/live` is a cheap process-level liveness check. It does not touch
PostgreSQL, object storage or SQS. A successful response means the API process
can serve HTTP and should not be restarted by Kubernetes because a dependency
is temporarily unavailable.

`GET /health/ready` checks three independent dependencies:

- PostgreSQL connectivity and the expected Alembic schema head;
- configured object storage bucket health;
- the configured analysis queue and its attributes.

It returns `200` with `status: ready` only when all checks pass. A dependency
failure returns `503` with `status: not_ready` and safe error class names; raw
connection strings and exception messages are not returned.

## Kubernetes and container behavior

The API Deployment uses:

```text
readiness -> /health/ready
liveness  -> /health/live
```

The API startup hook records dependency failures but does not terminate the
process. Kubernetes therefore removes an unready pod from service while still
allowing liveness and metrics diagnostics to work.

The worker writes `/tmp/ciis-worker-heartbeat` at startup and during every
poll loop. Docker and Kubernetes execute `python -m app.container_healthcheck`
for the worker; the check fails when the heartbeat is absent or older than the
configured threshold. This gives a stuck worker a restart signal even though
the worker has no HTTP server.

## Verification

```bash
./.venv/bin/python -m pytest backend/test_phase17_health.py -q
./.venv/bin/python -m pytest backend -q -ra
```

When the API is running:

```bash
curl -i http://127.0.0.1:8000/health/live
curl -i http://127.0.0.1:8000/health/ready
```

The readiness response is expected to be `503` when PostgreSQL, storage or
SQS is intentionally unavailable; that is a correct result, not an API
process failure.

## Boundary

This phase defines health semantics and probe wiring. It does not add an
external load balancer, HPA, PDB or alert policy; those can consume the stable
readiness and metric contracts in later deployment phases.
