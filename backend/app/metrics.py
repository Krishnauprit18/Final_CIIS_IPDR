from __future__ import annotations

import logging
import time
import uuid
from contextvars import Token

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.request_context import case_id_context, job_id_context, request_id_context


logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "ciis_http_requests_total",
    "Total HTTP requests processed by the API",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "ciis_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

ANALYSIS_JOBS_TOTAL = Counter(
    "ciis_analysis_jobs_total",
    "Analysis jobs observed by lifecycle status",
    ["job_type", "status"],
)
ANALYSIS_JOB_DURATION_SECONDS = Histogram(
    "ciis_analysis_job_duration_seconds",
    "Analysis job execution duration in seconds",
    ["job_type"],
)
FILES_UPLOADED_TOTAL = Counter(
    "ciis_files_uploaded_total",
    "Files accepted into durable analysis storage",
    ["kind"],
)
RECORDS_PROCESSED_TOTAL = Counter(
    "ciis_records_processed_total",
    "Normalized records processed by analysis workers",
)
WORKERS_ACTIVE = Gauge(
    "ciis_workers_active",
    "Whether this worker process is active",
)
SQS_QUEUE_DEPTH = Gauge(
    "ciis_sqs_queue_depth",
    "Approximate messages in the analysis queue",
    ["queue", "state"],
)


def set_job_context(job_id: int, case_id: int) -> tuple[Token, Token]:
    return (
        job_id_context.set(str(job_id)),
        case_id_context.set(str(case_id)),
    )


def reset_job_context(tokens: tuple[Token, Token]) -> None:
    job_token, case_token = tokens
    job_id_context.reset(job_token)
    case_id_context.reset(case_token)


def record_job_submitted(job_type: str) -> None:
    ANALYSIS_JOBS_TOTAL.labels(job_type=job_type, status="submitted").inc()


def record_job_finished(job_type: str, status: str, duration_seconds: float) -> None:
    ANALYSIS_JOBS_TOTAL.labels(job_type=job_type, status=status).inc()
    ANALYSIS_JOB_DURATION_SECONDS.labels(job_type=job_type).observe(duration_seconds)


def record_file_uploaded(kind: str) -> None:
    FILES_UPLOADED_TOTAL.labels(kind=kind).inc()


def record_records_processed(count: int) -> None:
    RECORDS_PROCESSED_TOTAL.inc(max(0, int(count)))


def set_worker_active(active: bool) -> None:
    WORKERS_ACTIVE.set(1 if active else 0)


def record_queue_depth(queue_name: str, attributes: dict) -> None:
    for state, key in (
        ("visible", "ApproximateNumberOfMessages"),
        ("in_flight", "ApproximateNumberOfMessagesNotVisible"),
    ):
        try:
            value = int(attributes.get(key, 0))
        except (TypeError, ValueError):
            value = 0
        SQS_QUEUE_DEPTH.labels(queue=queue_name, state=state).set(value)


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request_token = request_id_context.set(request_id)
    response = None
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        raise
    finally:
        duration = time.perf_counter() - start

        path = request.url.path

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status=str(status_code),
        ).inc()

        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=path,
        ).observe(duration)

        logger.info(
            "http_request",
            extra={
                "event": "http_request",
                "method": request.method,
                "path": path,
                "status": status_code,
                "duration_ms": round(duration * 1000, 3),
            },
        )
        request_id_context.reset(request_token)

    if response is not None:
        response.headers["X-Request-ID"] = request_id
        return response

    raise RuntimeError("request middleware completed without a response")


def metrics_endpoint() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
