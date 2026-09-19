# Phase 16 — Observability

CIIS now treats metrics, structured logs and traces as application features.

## Correlation

API requests accept or generate `X-Request-ID`. The request ID is returned to the caller and is included in JSON logs. Analysis submission copies the same ID into the SQS message. Workers restore `request_id`, `job_id` and `case_id` into logging context.

## Metrics

API metrics use route templates instead of raw paths to prevent high-cardinality series.

Key metrics:

- `ciis_http_requests_total`
- `ciis_http_request_duration_seconds`
- `ciis_analysis_jobs_total`
- `ciis_analysis_job_duration_seconds`
- `ciis_analysis_job_failures_total`
- `ciis_files_uploaded_total`
- `ciis_records_processed_total`
- `ciis_active_workers`
- `ciis_sqs_queue_depth`
- `ciis_sqs_messages_inflight`
- `ciis_db_pool_checked_out`
- `ciis_db_pool_size`

Worker metrics are exposed on port 9101.

## Logs

Important API/worker events use JSON logs. Correlation identifiers remain log fields rather than Prometheus labels.

## Traces

OpenTelemetry instruments FastAPI and SQLAlchemy. When `OTEL_EXPORTER_OTLP_ENDPOINT` is configured, spans are exported through the local OpenTelemetry Collector to Jaeger.

The Compose observability stack provides Prometheus on 9090, Grafana on 3000 and Jaeger on 16686.

## Verification

```bash
bash scripts/phase16-verify.sh
```
