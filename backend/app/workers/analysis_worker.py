from __future__ import annotations

import json
import tempfile
import time
import traceback
from pathlib import Path

import pandas as pd

from app.core.config import WORKER_POLL_SECONDS
from app.jobs.service import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)
from app.queue.sqs import (
    delete_analysis_message,
    receive_analysis_messages,
)
from app.storage.service import download_bytes, upload_bytes

from app.services.communication_mapping import CommunicationMapper
from app.services.data_normalizer import DataNormalizer
from app.services.suspicious_activity_detector import SuspiciousActivityDetector


def _write_temp_file(data: bytes, suffix: str = ".csv") -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=suffix,
        delete=False,
    )

    try:
        handle.write(data)
        handle.flush()
        return Path(handle.name)
    finally:
        handle.close()


def _load_dataset(dataset_bytes: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix or ".csv"

    temp_path = _write_temp_file(
        dataset_bytes,
        suffix=suffix,
    )

    try:
        normalizer = DataNormalizer()

        # Prefer the project's normalization pipeline.
        if hasattr(normalizer, "normalize_file"):
            result = normalizer.normalize_file(str(temp_path))

            if isinstance(result, pd.DataFrame):
                return result

            if isinstance(result, tuple):
                for item in result:
                    if isinstance(item, pd.DataFrame):
                        return item

        # CSV fallback keeps Phase 4 compatible with existing datasets.
        return pd.read_csv(temp_path)

    finally:
        temp_path.unlink(missing_ok=True)


def _run_analysis(df: pd.DataFrame) -> dict:
    if df.empty:
        raise ValueError("Dataset contains no rows")

    mapper = CommunicationMapper(df)
    detector = SuspiciousActivityDetector(df)

    result = {
        "rows": int(len(df)),
        "columns": list(df.columns),
    }

    try:
        mapping_stats = mapper.get_mapping_stats()
        result["mapping_stats"] = mapping_stats
    except Exception as exc:
        result["mapping_stats_error"] = str(exc)

    try:
        alerts = detector.run_comprehensive_analysis()
        result["alerts"] = alerts
        result["alert_count"] = len(alerts)
    except Exception as exc:
        result["alerts_error"] = str(exc)

    return result


def process_message(message: dict) -> None:
    body = json.loads(message["Body"])

    job_id = int(body["job_id"])
    case_id = int(body["case_id"])
    dataset_key = body["dataset_key"]

    dataset_filename = dataset_key.rsplit("/", 1)[-1]

    receive_count = int(
        message.get("Attributes", {}).get(
            "ApproximateReceiveCount",
            "1",
        )
    )

    print(
        f"[worker] job={job_id} "
        f"case={case_id} "
        f"attempt={receive_count}"
    )

    mark_job_running(job_id)

    try:
        dataset_bytes = download_bytes(dataset_key)

        df = _load_dataset(
            dataset_bytes,
            dataset_filename,
        )

        result = _run_analysis(df)

        result_payload = {
            "job_id": job_id,
            "case_id": case_id,
            "status": "SUCCEEDED",
            "analysis": result,
        }

        result_key = (
            f"analysis-results/{case_id}/{job_id}/result.json"
        )

        upload_bytes(
            json.dumps(
                result_payload,
                default=str,
                indent=2,
            ).encode("utf-8"),
            result_key,
            content_type="application/json",
        )

        mark_job_succeeded(job_id)

        delete_analysis_message(
            message["ReceiptHandle"]
        )

        print(
            f"[worker] job={job_id} succeeded "
            f"result=s3://analysis-results/{case_id}/{job_id}"
        )

    except Exception as exc:
        print(
            f"[worker] job={job_id} failed: {exc}"
        )

        traceback.print_exc()

        # Important:
        # Message ko delete NAHI karenge.
        # SQS visibility timeout ke baad message retry hoga.
        #
        # maxReceiveCount=3 ke baad LocalStack/AWS SQS
        # message ko DLQ me bhej dega.

        if receive_count >= 3:
            mark_job_failed(
                job_id,
                str(exc),
            )

        raise


def run_worker() -> None:
    print("[worker] CIIS analysis worker started")
    print("[worker] waiting for SQS messages...")

    while True:
        try:
            messages = receive_analysis_messages(
                wait_time_seconds=WORKER_POLL_SECONDS,
                max_messages=1,
            )

            if not messages:
                continue

            for message in messages:
                try:
                    process_message(message)
                except Exception:
                    # Failure intentionally swallowed here so worker
                    # process itself stays alive.
                    pass

        except KeyboardInterrupt:
            print("\n[worker] shutting down")
            break

        except Exception as exc:
            print(
                f"[worker] queue error: {exc}"
            )

            time.sleep(5)


if __name__ == "__main__":
    run_worker()