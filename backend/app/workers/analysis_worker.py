from __future__ import annotations

import json
import logging
import os
import socket
import tempfile
import time
import uuid
from pathlib import Path

import pandas as pd

from app.core.config import WORKER_POLL_SECONDS, WORKER_VISIBILITY_TIMEOUT
from app.core.logging import configure_logging
from app.workers.health import touch_worker_heartbeat
from app.metrics import (
    record_job_finished,
    record_records_processed,
    reset_job_context,
    set_job_context,
    set_worker_active,
)
from app.jobs.service import (
    claim_analysis_job,
    complete_job,
    fail_job,
    retry_job,
    set_job_progress,
)
from app.queue.sqs import delete_analysis_message, receive_analysis_messages
from app.storage.service import download_bytes, storage_uri, upload_bytes
from app.services.communication_mapping import CommunicationMapper
from app.services.data_normalizer import DataNormalizer
from app.services.suspicious_activity_detector import SuspiciousActivityDetector


MAX_RECEIVE_COUNT = 3
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
logger = logging.getLogger(__name__)


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
    dataset_key = body["dataset_key"]
    dataset_filename = dataset_key.rsplit("/", 1)[-1]
    receive_count = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))

    logger.info(
        "job_received",
        extra={"event": "job_received", "worker_id": worker_id},
    )

    claimed = claim_analysis_job(
        job_id,
        worker_id,
        lease_seconds=WORKER_VISIBILITY_TIMEOUT,
    )

    if claimed is None:
        # Either the job is missing or another worker owns a live lease. Do not
        # acknowledge; SQS will redeliver after visibility timeout.
        logger.info("job_not_claimable", extra={"event": "job_not_claimable"})
        return

    if claimed["status"] == "SUCCEEDED":
        # Crash-after-DB-commit-before-SQS-ack: the duplicate is safe to ack.
        logger.info("job_duplicate_succeeded", extra={"event": "job_duplicate_succeeded"})
        delete_analysis_message(message["ReceiptHandle"])
        return

    if claimed["status"] == "FAILED":
        # Failed jobs must remain eligible for SQS redrive to the DLQ.
        logger.info("job_already_failed", extra={"event": "job_already_failed"})
        return

    job_started = time.perf_counter()
    context_tokens = set_job_context(job_id, case_id)
    try:
        set_job_progress(job_id, worker_id, 10)
        dataset_bytes = download_bytes(dataset_key)

        set_job_progress(job_id, worker_id, 35)
        df = _load_dataset(dataset_bytes, dataset_filename)
        try:
            record_records_processed(len(df))
        except TypeError:
            # Keep compatibility with lightweight worker unit-test doubles;
            # production datasets are always sized DataFrames.
            pass

        set_job_progress(job_id, worker_id, 65)
        result = _run_analysis(df)

        result_payload = {
            "job_id": job_id,
            "case_id": case_id,
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

        # DB completion happens before SQS acknowledgement. If the process dies
        # after this commit but before delete_message, a duplicate delivery sees
        # SUCCEEDED and acknowledges without repeating analysis.
        if not complete_job(job_id, worker_id, result_uri):
            raise RuntimeError(f"Lost claim while completing job {job_id}")

        delete_analysis_message(message["ReceiptHandle"])
        record_job_finished("CASE_ANALYSIS", "succeeded", time.perf_counter() - job_started)
        logger.info("job_succeeded", extra={"event": "job_succeeded", "worker_id": worker_id})

    except Exception as exc:
        record_job_finished("CASE_ANALYSIS", "failed", time.perf_counter() - job_started)
        logger.exception("job_failed", extra={"event": "job_failed", "worker_id": worker_id})

        if receive_count >= MAX_RECEIVE_COUNT:
            fail_job(job_id, worker_id, str(exc))
        else:
            retry_job(job_id, worker_id, str(exc))

        # Never acknowledge a failed attempt. Visibility timeout provides retry;
        # the queue redrive policy moves the third failed delivery to the DLQ.
        raise
    finally:
        reset_job_context(context_tokens)


def run_worker() -> None:
    configure_logging()
    touch_worker_heartbeat()
    set_worker_active(True)
    logger.info("worker_started", extra={"event": "worker_started", "worker_id": WORKER_ID})

    while True:
        try:
            touch_worker_heartbeat()
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
            logger.info("worker_shutdown", extra={"event": "worker_shutdown", "worker_id": WORKER_ID})
            break
        except Exception as exc:
            logger.exception("queue_error", extra={"event": "queue_error", "worker_id": WORKER_ID})
            time.sleep(5)
    set_worker_active(False)


if __name__ == "__main__":
    run_worker()
