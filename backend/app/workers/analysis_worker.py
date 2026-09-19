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
    request_id = body.get("request_id")
    dataset_key = body["dataset_key"]
    dataset_filename = dataset_key.rsplit("/", 1)[-1]
    receive_count = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))

    request_token = request_id_var.set(request_id)
    job_token = job_id_var.set(str(job_id))
    case_token = case_id_var.set(str(case_id))
    started = time.perf_counter()

    logger.info(
        f"job receive={receive_count} worker={worker_id}",
        extra={"event": "job_received"},
    )

    try:
        claimed = claim_analysis_job(
            job_id,
            worker_id,
            lease_seconds=WORKER_VISIBILITY_TIMEOUT,
        )

        if claimed is None:
            logger.info(
                "job not claimable; leaving message unacked",
                extra={"event": "job_not_claimable"},
            )
            return

        if claimed["status"] == "SUCCEEDED":
            logger.info(
                "job already succeeded; acknowledging duplicate",
                extra={"event": "job_duplicate_ack"},
            )
            delete_analysis_message(message["ReceiptHandle"])
            return

        if claimed["status"] == "FAILED":
            logger.info(
                "job already failed; leaving message for DLQ redrive",
                extra={"event": "job_already_failed"},
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
                "request_id": request_id,
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
                f"job succeeded result={result_uri}",
                extra={"event": "job_succeeded"},
            )

        except Exception as exc:
            ANALYSIS_JOB_FAILURES_TOTAL.inc()
            ANALYSIS_JOBS_TOTAL.labels(status="failed_attempt").inc()
            logger.exception(
                f"job failed: {exc}",
                extra={"event": "job_failed"},
            )

            if receive_count >= MAX_RECEIVE_COUNT:
                fail_job(job_id, worker_id, str(exc))
            else:
                retry_job(job_id, worker_id, str(exc))
            raise

    finally:
        ANALYSIS_JOB_DURATION_SECONDS.observe(time.perf_counter() - started)
        request_id_var.reset(request_token)
        job_id_var.reset(job_token)
        case_id_var.reset(case_token)


def run_worker() -> None:
    configure_logging()
    start_worker_metrics_server()
    ACTIVE_WORKERS.inc()

    logger.info(
        f"CIIS analysis worker started id={WORKER_ID}",
        extra={"event": "worker_started"},
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
            except Exception as exc:
                logger.exception(
                    f"queue error: {exc}",
                    extra={"event": "worker_queue_error"},
                )
                time.sleep(5)
    finally:
        ACTIVE_WORKERS.dec()


if __name__ == "__main__":
    run_worker()
