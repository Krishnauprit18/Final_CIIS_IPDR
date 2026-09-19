from __future__ import annotations

import json
import os
import socket
import tempfile
import time
import uuid
from pathlib import Path

import pandas as pd

from app.core.config import WORKER_POLL_SECONDS, WORKER_VISIBILITY_TIMEOUT
from app.core.context import case_id_var, job_id_var, request_id_var
from app.core.logging import configure_logging, get_logger
from app.jobs.service import (
    claim_analysis_job,
    complete_job,
    fail_job,
    retry_job,
    set_job_progress,
)
from app.metrics import (
    ACTIVE_WORKERS,
    ANALYSIS_JOB_DURATION_SECONDS,
    ANALYSIS_JOB_FAILURES_TOTAL,
    ANALYSIS_JOBS_TOTAL,
    RECORDS_PROCESSED_TOTAL,
    start_worker_metrics_server,
)
from app.observability.tracing import configure_worker_tracing, get_tracer
from app.queue.sqs import delete_analysis_message, receive_analysis_messages
from app.storage.service import download_bytes, storage_uri, upload_bytes
from app.services.communication_mapping import CommunicationMapper
from app.services.data_normalizer import DataNormalizer
from app.services.suspicious_activity_detector import SuspiciousActivityDetector


MAX_RECEIVE_COUNT = 3
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
logger = get_logger(__name__)


def _write_temp_file(data: bytes, suffix: str = ".csv") -> Path:
    handle = tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False)
    try:
        handle.write(data)
        handle.flush()
        return Path(handle.name)
    finally:
        handle.close()


def _load_dataset(dataset_bytes: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix or ".csv"
    temp_path = _write_temp_file(dataset_bytes, suffix=suffix)
    try:
        return DataNormalizer().normalize_file(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


def _run_analysis(df: pd.DataFrame) -> dict:
    if df.empty:
        raise ValueError("Dataset contains no rows")

    mapper = CommunicationMapper(df)
    detector = SuspiciousActivityDetector(df)
    result = {"rows": int(len(df)), "columns": list(df.columns)}

    try:
        result["mapping_stats"] = mapper.get_mapping_stats()
    except Exception as exc:
        result["mapping_stats_error"] = str(exc)

    try:
        alerts = detector.run_comprehensive_analysis()
        result["alerts"] = alerts
        result["alert_count"] = len(alerts)
    except Exception as exc:
        result["alerts_error"] = str(exc)

    return result


def process_message(message: dict, *, worker_id: str = WORKER_ID) -> None:
    body = json.loads(message["Body"])
    job_id = int(body["job_id"])
    case_id = int(body["case_id"])
    request_id = str(body.get("request_id") or "")
    dataset_key = body["dataset_key"]
    dataset_filename = dataset_key.rsplit("/", 1)[-1]
    receive_count = int(
        message.get("Attributes", {}).get("ApproximateReceiveCount", "1")
    )

    request_token = request_id_var.set(request_id or None)
    job_token = job_id_var.set(str(job_id))
    case_token = case_id_var.set(str(case_id))
    started = time.perf_counter()
    tracer = get_tracer(__name__)

    try:
        ANALYSIS_JOBS_TOTAL.labels(status="received").inc()
        logger.info(
            "analysis job received",
            extra={
                "event": "job_received",
                "receive_count": receive_count,
                "worker_id": worker_id,
            },
        )

        with tracer.start_as_current_span("ciis.analysis_job") as span:
            span.set_attribute("ciis.job_id", job_id)
            span.set_attribute("ciis.case_id", case_id)
            span.set_attribute("ciis.receive_count", receive_count)

            claimed = claim_analysis_job(
                job_id,
                worker_id,
                lease_seconds=WORKER_VISIBILITY_TIMEOUT,
            )

            if claimed is None:
                logger.info(
                    "analysis job not claimable",
                    extra={"event": "job_not_claimable", "worker_id": worker_id},
                )
                return

            if claimed["status"] == "SUCCEEDED":
                delete_analysis_message(message["ReceiptHandle"])
                ANALYSIS_JOBS_TOTAL.labels(status="duplicate_ack").inc()
                logger.info(
                    "duplicate successful job acknowledged",
                    extra={"event": "job_duplicate_ack"},
                )
                return

            if claimed["status"] == "FAILED":
                logger.info(
                    "failed job left for DLQ redrive",
                    extra={"event": "job_failed_redrive"},
                )
                return

            try:
                set_job_progress(job_id, worker_id, 10)
                dataset_bytes = download_bytes(dataset_key)

                set_job_progress(job_id, worker_id, 35)
                df = _load_dataset(dataset_bytes, dataset_filename)
                RECORDS_PROCESSED_TOTAL.inc(len(df))

                set_job_progress(job_id, worker_id, 65)
                result = _run_analysis(df)

                result_payload = {
                    "job_id": job_id,
                    "case_id": case_id,
                    "request_id": request_id or None,
                    "status": "SUCCEEDED",
                    "analysis": result,
                }
                result_key = f"analysis-results/{case_id}/{job_id}/result.json"

                set_job_progress(job_id, worker_id, 90)
                upload_bytes(
                    json.dumps(result_payload, default=str, indent=2).encode("utf-8"),
                    result_key,
                    content_type="application/json",
                )
                result_uri = storage_uri(result_key)

                if not complete_job(job_id, worker_id, result_uri):
                    raise RuntimeError(f"Lost claim while completing job {job_id}")

                delete_analysis_message(message["ReceiptHandle"])
                ANALYSIS_JOBS_TOTAL.labels(status="succeeded").inc()
                logger.info(
                    "analysis job succeeded",
                    extra={"event": "job_succeeded", "result_uri": result_uri},
                )

            except Exception:
                ANALYSIS_JOB_FAILURES_TOTAL.inc()
                ANALYSIS_JOBS_TOTAL.labels(status="attempt_failed").inc()
                logger.exception(
                    "analysis job attempt failed",
                    extra={
                        "event": "job_failed",
                        "receive_count": receive_count,
                    },
                )

                if receive_count >= MAX_RECEIVE_COUNT:
                    fail_job(job_id, worker_id, "analysis attempt failed")
                else:
                    retry_job(job_id, worker_id, "analysis attempt failed")
                raise
    finally:
        ANALYSIS_JOB_DURATION_SECONDS.observe(time.perf_counter() - started)
        case_id_var.reset(case_token)
        job_id_var.reset(job_token)
        request_id_var.reset(request_token)


def run_worker() -> None:
    configure_logging()
    configure_worker_tracing()
    start_worker_metrics_server()
    ACTIVE_WORKERS.inc()

    logger.info(
        "CIIS analysis worker started",
        extra={"event": "worker_started", "worker_id": WORKER_ID},
    )

    try:
        while True:
            try:
                messages = receive_analysis_messages(
                    wait_time_seconds=WORKER_POLL_SECONDS,
                    max_messages=1,
                )
                for message in messages:
                    try:
                        process_message(message)
                    except Exception:
                        pass
            except KeyboardInterrupt:
                logger.info("worker shutting down", extra={"event": "worker_shutdown"})
                break
            except Exception:
                logger.exception(
                    "worker queue error",
                    extra={"event": "queue_error"},
                )
                time.sleep(5)
    finally:
        ACTIVE_WORKERS.dec()


if __name__ == "__main__":
    run_worker()
