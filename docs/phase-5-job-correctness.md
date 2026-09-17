# Phase 5 — Idempotency and job correctness

Phase 5 makes SQS at-least-once delivery safe for expensive IPDR analysis.

## State machine

```text
QUEUED -> RUNNING -> SUCCEEDED
            |
            +------> FAILED

A non-terminal failed attempt releases its claim and returns to QUEUED.
```

## Claim protocol

1. Worker receives an SQS message containing `job_id`.
2. Worker opens a PostgreSQL transaction and locks the matching `jobs` row with `SELECT ... FOR UPDATE`.
3. A `QUEUED` job, or a `RUNNING` job whose lease expired, is claimed by setting `worker_id`, `claim_expires_at`, `RUNNING`, and incrementing `attempt_count`.
4. A live claim owned by another worker is not processed.
5. A `SUCCEEDED` duplicate is acknowledged immediately without analysis.
6. Analysis writes its result to the deterministic object key `analysis-results/{case_id}/{job_id}/result.json`.
7. The worker commits `SUCCEEDED`, `progress=100`, and `result_uri` in PostgreSQL before acknowledging SQS.
8. If the process crashes after the DB commit but before SQS acknowledgement, redelivery observes `SUCCEEDED` and only acknowledges the duplicate.

## Failure protocol

- First/second failed receive: release claim, return DB state to `QUEUED`, keep SQS message unacknowledged.
- Third failed receive: commit `FAILED`, keep the message unacknowledged so the queue redrive policy moves it to the DLQ.
- A worker crash leaves a `RUNNING` lease. After `claim_expires_at`, a replacement worker may reclaim the job.

## Progress

Worker checkpoints are persisted in `jobs.progress`:

- 0: queued
- 1: claimed
- 10: downloading input
- 35: normalizing
- 65: analytics
- 90: persisting result
- 100: succeeded

This allows the frontend to show durable status without reading worker memory.

## Migration

```bash
cd backend
alembic upgrade head
alembic current
```

Expected head:

```text
0002_phase5_job_correctness (head)
```

## Acceptance

```bash
python -m compileall -q app
python -m pytest -q
```

Then run API + two worker processes and submit the same SQS message twice. Only one worker should obtain the live database claim. Test a worker crash after result/DB completion but before acknowledgement; the redelivered message must not repeat analysis.
