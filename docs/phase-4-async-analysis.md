# Phase 4 — Asynchronous analysis with SQS

## Goal

Move heavy IPDR analysis out of the FastAPI request process so large files do not keep an HTTP request open while Pandas normalization, graph construction, and anomaly detection run.

```text
Upload
  |
  v
FastAPI
  |  store input in S3/MinIO
  |  create jobs row (QUEUED)
  |  send SQS message
  v
202 Accepted

SQS main queue
  |
  v
analysis worker
  |  download input
  |  normalize
  |  communication mapping / correlation
  |  suspicious activity detection
  |  persist result JSON to object storage
  |  persist result URI on job
  v
SUCCEEDED
```

Failures are not acknowledged. SQS retries the message and, after `maxReceiveCount=3`, moves it to `ciis-analysis-dlq`.

## Components

- `compose.queue.yaml` — LocalStack SQS for local development.
- `infra/localstack/init-sqs.sh` — creates the main queue and DLQ with a redrive policy.
- `app/queue/sqs.py` — boto3 SQS boundary.
- `app/jobs/service.py` — job lifecycle service.
- `app/api/routers/jobs.py` — async submission and job-status API.
- `app/workers/analysis_worker.py` — independently running Python worker.
- PostgreSQL `jobs` table — durable state (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`).
- MinIO/S3 — durable input and result objects.

## API

### Submit analysis

```http
POST /cases/{case_id}/analysis
Content-Type: multipart/form-data
```

Required form field: `dataset_file`.
Optional form field: `case_file`.

Successful response:

```http
202 Accepted
```

```json
{
  "job_id": 123,
  "status": "queued"
}
```

The response is returned after durable upload + job creation + SQS enqueue. Heavy analysis runs in the worker.

### Query status

```http
GET /jobs/{job_id}
```

On success the job payload includes the persisted result URI, for example:

```json
{
  "id": 123,
  "status": "SUCCEEDED",
  "payload": {
    "case_id": 1,
    "dataset_key": "analysis-inputs/1/.../synthetic.csv",
    "case_file_key": null,
    "result_uri": "s3://ciis-storage/analysis-results/1/123/result.json"
  }
}
```

## Local services

From the repository root:

```bash
docker compose -f compose.db.yaml up -d
docker compose -f compose.storage.yaml up -d
docker compose -f compose.queue.yaml up -d
```

Verify:

```bash
docker compose -f compose.db.yaml ps
docker compose -f compose.storage.yaml ps -a
docker compose -f compose.queue.yaml ps
docker exec ciis-localstack awslocal sqs list-queues
```

Expected queues:

- `ciis-analysis`
- `ciis-analysis-dlq`

## Start API and worker

API terminal:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Worker terminal:

```bash
cd backend
python -m app.workers.analysis_worker
```

The API now verifies PostgreSQL, object storage, and the analysis queue during startup.

## Happy-path smoke test

Use an existing case ID:

```bash
curl -i -X POST \
  "http://127.0.0.1:8000/cases/1/analysis" \
  -F "dataset_file=@Scenario A1-ARFF/synthetic.csv"
```

Poll the returned job ID:

```bash
curl http://127.0.0.1:8000/jobs/<JOB_ID>
```

Expected lifecycle:

```text
QUEUED -> RUNNING -> SUCCEEDED
```

The worker writes:

```text
analysis-results/<case_id>/<job_id>/result.json
```

into the configured S3-compatible bucket.

## DLQ smoke test

The normal worker visibility timeout is intentionally long for real heavy analysis. For a fast local DLQ test, stop the normal worker and run a temporary worker with a two-second visibility timeout:

```bash
cd backend
WORKER_VISIBILITY_TIMEOUT=2 WORKER_POLL_SECONDS=1 \
  python -m app.workers.analysis_worker
```

Create a real job with a deliberately missing object and enqueue it:

```bash
python - <<'PY'
from app.db.repositories import create_job_record
from app.queue.sqs import send_analysis_message

job = create_job_record(
    case_id=1,
    job_type="CASE_ANALYSIS",
    payload={
        "case_id": 1,
        "dataset_key": "analysis-inputs/does-not-exist.csv",
        "case_file_key": None,
    },
)

send_analysis_message({
    "job_id": job["id"],
    "case_id": 1,
    "dataset_key": "analysis-inputs/does-not-exist.csv",
    "case_file_key": None,
})

print(job["id"])
PY
```

The worker should log attempts 1, 2, and 3. The job becomes `FAILED` on the third failure and SQS moves the message to the DLQ.

Check the DLQ:

```bash
DLQ_URL=$(docker exec ciis-localstack \
  awslocal sqs get-queue-url \
  --queue-name ciis-analysis-dlq \
  --query QueueUrl \
  --output text)

docker exec ciis-localstack \
  awslocal sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages
```

Expected after redrive:

```json
{
  "Attributes": {
    "ApproximateNumberOfMessages": "1"
  }
}
```

## Automated tests

```bash
cd backend
python -m compileall -q app
python -m pytest -q
```

Phase 4 tests cover job state transitions, successful enqueue, enqueue failure cleanup, successful worker acknowledgement, result URI persistence, and third-attempt failure behavior.

## AWS production mapping

Local development uses LocalStack through `SQS_ENDPOINT_URL=http://localhost:4566`. In AWS, leave `SQS_ENDPOINT_URL`, `SQS_ACCESS_KEY`, and `SQS_SECRET_KEY` empty and use the normal boto3 credential provider chain/IAM role. The application code remains the same.

The worker is a separate Python process and can be scaled independently from the API. Multiple workers may consume the same SQS queue; duplicate successful deliveries are acknowledged without repeating analysis.

## Phase 4 acceptance criteria

- `POST /cases/{id}/analysis` returns `202 Accepted` without running heavy analysis in the request process.
- Input artifacts are durable in S3/MinIO before enqueue.
- A durable PostgreSQL `jobs` row tracks state.
- SQS carries the work message.
- The worker performs normalization, mapping/correlation, and anomaly detection independently.
- Results are persisted in object storage and exposed through `GET /jobs/{job_id}` as `result_uri`.
- Successful messages are acknowledged.
- Failed messages are retried and moved to the DLQ after three receives.
- Duplicate successful SQS delivery does not rerun the analysis.
- Existing tests and Phase 4 tests pass before merge.
