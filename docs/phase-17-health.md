# Phase 17 — Health semantics

## API

`/health/live` proves the API process can answer HTTP and does not call PostgreSQL, S3 or SQS.

`/health/ready` checks PostgreSQL, object storage and SQS. A dependency failure returns HTTP 503 while liveness remains HTTP 200.

Transient storage/queue checks are not startup blockers; Kubernetes readiness gates traffic.

## Worker

The worker health server listens on port 9102.

- `/health/live` checks the main polling-loop heartbeat.
- `/health/ready` checks PostgreSQL, S3 and SQS.

## Kubernetes probes

API and worker each use separate startup, readiness and liveness probes.

## Failure lab

```bash
bash scripts/phase17-failure-test.sh
```

The lab stops PostgreSQL, requires liveness to remain 200, requires readiness to become 503, restores PostgreSQL, and requires readiness to recover.
