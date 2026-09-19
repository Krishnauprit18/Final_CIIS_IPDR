from __future__ import annotations

import os
import threading
import time

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    start_http_server,
)

HTTP_REQUESTS_TOTAL = Counter(
    "ciis_http_requests_total",
    "Total HTTP requests processed by the API",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "ciis_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
)

ANALYSIS_JOBS_TOTAL = Counter(
    "ciis_analysis_jobs_total",
    "Analysis jobs by terminal outcome",
    ["status"],
)

ANALYSIS_JOB_DURATION_SECONDS = Histogram(
    "ciis_analysis_job_duration_seconds",
    "Analysis job processing duration in seconds",
)

ANALYSIS_JOB_FAILURES_TOTAL = Counter(
    "ciis_analysis_job_failures_total",
    "Total failed analysis attempts",
)

FILES_UPLOADED_TOTAL = Counter(
    "ciis_files_uploaded_total",
    "Total files uploaded for asynchronous analysis",
)

RECORDS_PROCESSED_TOTAL = Counter(
    "ciis_records_processed_total",
    "Total normalized records processed by workers",
)

ACTIVE_WORKERS = Gauge(
    "ciis_active_workers",
    "Active CIIS worker processes",
)

SQS_QUEUE_DEPTH = Gauge(
    "ciis_sqs_queue_depth",
    "Approximate number of visible analysis messages",
)

SQS_MESSAGES_INFLIGHT = Gauge(
    "ciis_sqs_messages_inflight",
    "Approximate number of in-flight analysis messages",
)

DB_POOL_CHECKED_OUT = Gauge(
    "ciis_db_pool_checked_out",
    "Checked-out SQLAlchemy connections",
)

DB_POOL_SIZE = Gauge(
    "ciis_db_pool_size",
    "Configured SQLAlchemy connection pool size",
)

_collector_started = False
_collector_lock = threading.Lock()


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    return str(template) if template else "unmatched"


def record_job_submitted(job_type: str) -> None:
    ANALYSIS_JOBS_TOTAL.labels(status="submitted").inc()


def record_job_finished(job_type: str, status: str, duration_seconds: float) -> None:
    ANALYSIS_JOBS_TOTAL.labels(status=status).inc()
    ANALYSIS_JOB_DURATION_SECONDS.observe(duration_seconds)


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = _route_label(request)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            route=route,
            status=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            route=route,
        ).observe(duration)


def _collect_runtime_metrics() -> None:
    try:
        from app.db.session import get_engine
        pool = get_engine().pool
        checked_out = getattr(pool, "checkedout", None)
        size = getattr(pool, "size", None)
        if callable(checked_out):
            DB_POOL_CHECKED_OUT.set(float(checked_out()))
        if callable(size):
            DB_POOL_SIZE.set(float(size()))
    except Exception:
        pass

    try:
        from app.queue.sqs import get_queue_metrics
        values = get_queue_metrics()
        SQS_QUEUE_DEPTH.set(values["visible"])
        SQS_MESSAGES_INFLIGHT.set(values["inflight"])
    except Exception:
        pass


def _collector_loop() -> None:
    interval = max(5, int(os.getenv("METRICS_COLLECTION_SECONDS", "15")))
    while True:
        _collect_runtime_metrics()
        time.sleep(interval)


def start_background_metrics_collector() -> None:
    global _collector_started
    with _collector_lock:
        if _collector_started:
            return
        threading.Thread(
            target=_collector_loop,
            name="ciis-metrics-collector",
            daemon=True,
        ).start()
        _collector_started = True


def start_worker_metrics_server() -> None:
    port = int(os.getenv("WORKER_METRICS_PORT", "9101"))
    start_http_server(port)
    start_background_metrics_collector()


def metrics_endpoint() -> Response:
    _collect_runtime_metrics()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
