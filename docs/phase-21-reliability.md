# Phase 21 — Reliability and failure laboratories

## What is implemented

- SQS remains at-least-once and the worker keeps the existing database claim
  lease, retry count, and DLQ redrive contract.
- A successful duplicate delivery is acknowledged without re-running analysis.
- A missing object is classified as a permanent `MISSING_OBJECT` job failure
  and the message is acknowledged instead of looping forever.
- An empty or entirely unusable normalized IPDR file is classified as
  `INVALID_INPUT`, copied to `quarantine/<case>/<job>/<hash>-<name>`, and the
  job is failed cleanly.
- Input and result SHA-256 values are persisted in the job record and also
  retained in the job payload for API visibility.
- API and worker Kubernetes probes already provide the replacement/readiness
  boundary used by the labs.

## Reproducible labs

The commands are intentionally guarded. They can delete a pod or scale the
local PostgreSQL deployment and must be run only against the local lab context.

```bash
RUN_DESTRUCTIVE_LAB=1 bash scripts/failure-labs/kubernetes-recovery.sh kill-api
RUN_DESTRUCTIVE_LAB=1 bash scripts/failure-labs/kubernetes-recovery.sh kill-worker
RUN_DESTRUCTIVE_LAB=1 bash scripts/failure-labs/kubernetes-recovery.sh db-outage
```

For each run, capture the command output and complete the matching record in
`docs/failure-labs/`. No reliability claim is complete without the observed
pod/job/queue output.

## Deliberately not claimed

This phase does not claim that a live Kubernetes pod was killed or that a
specific queue backlog was drained. Those are environment-specific experiments
and remain manual evidence runs.
