# Phase 16 — Observability

## HTTP correlation

Every API request receives an `X-Request-ID` response header. A caller-supplied
`X-Request-ID` is preserved; otherwise the API creates a UUID. The request ID
is held in a context variable so JSON log records emitted during the request
carry the same value.

Worker execution carries `job_id` and `case_id` context values. These values
are identifiers only; input data, bearer tokens and secret values are not
logged.

## Metrics

The existing `/metrics` endpoint remains Prometheus-compatible. In addition to
HTTP count/latency metrics, the API and worker now expose:

- submitted/succeeded/failed analysis jobs and execution duration;
- accepted dataset/case-document upload counts;
- normalized records processed;
- active worker-process state;
- visible and in-flight SQS depth;
- request count, status and latency.

Prometheus continues to scrape the API using
`observability/prometheus/prometheus.yml`; Grafana can use Prometheus as its
data source in the Compose or Kubernetes lab.

## Structured logs

`app/core/logging.py` configures a compact JSON formatter with UTC timestamp,
level, logger, message and selected event fields. Worker `print` statements
were replaced with structured logger calls, including exception traces for
failures. This format is suitable for a container runtime or a later log
collector without requiring an application rewrite.

## Verification

```bash
./.venv/bin/python -m pytest backend/test_phase16_observability.py -q
./.venv/bin/python -m pytest backend -q -ra
```

Live verification, when the local stack is available:

```bash
curl -i http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/metrics
```

The first response should contain `X-Request-ID`; the second should contain
`ciis_http_requests_total` and the domain metric families after the API and
worker have handled traffic.

## Boundary

Phase 16 establishes application-level metrics, JSON logs and correlation
fields. Distributed tracing/exporters, alert rules, dashboards as code and a
central log backend can be added later without changing the metric names or
request/job correlation contract.
