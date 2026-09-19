import json
import logging

from app.core.context import case_id_var, job_id_var, request_id_var
from app.core.logging import JsonFormatter
from app.metrics import (
    ANALYSIS_JOBS_TOTAL,
    DB_POOL_CHECKED_OUT,
    HTTP_REQUESTS_TOTAL,
    RECORDS_PROCESSED_TOTAL,
    SQS_QUEUE_DEPTH,
)


def test_phase16_metric_names_are_stable():
    assert HTTP_REQUESTS_TOTAL._name == "ciis_http_requests"
    assert ANALYSIS_JOBS_TOTAL._name == "ciis_analysis_jobs"
    assert RECORDS_PROCESSED_TOTAL._name == "ciis_records_processed"
    assert SQS_QUEUE_DEPTH._name == "ciis_sqs_queue_depth"
    assert DB_POOL_CHECKED_OUT._name == "ciis_db_pool_checked_out"


def test_phase16_json_logs_include_correlation_context():
    request_token = request_id_var.set("request-123")
    job_token = job_id_var.set("44")
    case_token = case_id_var.set("12")
    try:
        record = logging.LogRecord(
            name="ciis.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.event = "test_event"
        record.worker_id = "worker-a"

        payload = json.loads(JsonFormatter().format(record))

        assert payload["request_id"] == "request-123"
        assert payload["job_id"] == "44"
        assert payload["case_id"] == "12"
        assert payload["event"] == "test_event"
        assert payload["worker_id"] == "worker-a"
    finally:
        case_id_var.reset(case_token)
        job_id_var.reset(job_token)
        request_id_var.reset(request_token)
