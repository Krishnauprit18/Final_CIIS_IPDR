import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

from starlette.responses import Response

from app.core.logging import JsonFormatter
from app.metrics import metrics_middleware


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_json_logs_include_correlation_context(monkeypatch):
    from app.core.request_context import request_id_context

    token = request_id_context.set("request-test-1")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="request complete",
            args=(),
            exc_info=None,
        )
        record.event = "test_event"
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)

    assert payload["request_id"] == "request-test-1"
    assert payload["event"] == "test_event"
    assert "password" not in json.dumps(payload).lower()


def test_http_middleware_returns_request_id_header():
    request = SimpleNamespace(
        method="GET",
        headers={},
        url=SimpleNamespace(path="/health/live"),
    )

    async def call_next(_request):
        return Response(content="ok", status_code=200)

    response = asyncio.run(metrics_middleware(request, call_next))

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_phase16_has_domain_metrics_and_structured_worker_logging():
    metrics = (PROJECT_ROOT / "backend" / "app" / "metrics.py").read_text(
        encoding="utf-8"
    )
    worker = (
        PROJECT_ROOT / "backend" / "app" / "workers" / "analysis_worker.py"
    ).read_text(encoding="utf-8")

    for name in (
        "ciis_analysis_jobs_total",
        "ciis_analysis_job_duration_seconds",
        "ciis_files_uploaded_total",
        "ciis_records_processed_total",
        "ciis_workers_active",
        "ciis_sqs_queue_depth",
    ):
        assert name in metrics

    assert "logger.exception" in worker
    assert "print(" not in worker
