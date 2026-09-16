from __future__ import annotations

import json
from typing import Any

from app.db.repositories import (
    create_job_record,
    get_job_record,
    update_job_payload,
    update_job_status,
)


def create_analysis_job(
    *,
    case_id: int,
    dataset_key: str,
    case_file_key: str | None,
) -> dict[str, Any]:
    payload = {
        "case_id": case_id,
        "dataset_key": dataset_key,
        "case_file_key": case_file_key,
    }

    return create_job_record(
        case_id=case_id,
        job_type="CASE_ANALYSIS",
        payload=payload,
    )


def get_job(job_id: int) -> dict[str, Any] | None:
    job = get_job_record(job_id)

    if not job:
        return None

    if job.get("payload_json"):
        job["payload"] = json.loads(job["payload_json"])

    job.pop("payload_json", None)

    return job


def set_job_result(job_id: int, result_uri: str) -> None:
    job = get_job_record(job_id)
    if not job:
        raise KeyError(job_id)

    payload = json.loads(job.get("payload_json") or "{}")
    payload["result_uri"] = result_uri
    update_job_payload(job_id, payload)


def mark_job_running(job_id: int) -> None:
    update_job_status(
        job_id,
        "RUNNING",
        error_message=None,
    )


def mark_job_retrying(job_id: int, error: str) -> None:
    # The message remains in SQS and becomes visible again after the
    # visibility timeout. QUEUED accurately represents that waiting state.
    update_job_status(
        job_id,
        "QUEUED",
        error_message=error[:2000],
    )


def mark_job_succeeded(job_id: int) -> None:
    update_job_status(
        job_id,
        "SUCCEEDED",
        error_message=None,
    )


def mark_job_failed(
    job_id: int,
    error: str,
) -> None:
    update_job_status(
        job_id,
        "FAILED",
        error_message=error[:2000],
    )


def job_is_terminal(job_id: int) -> bool:
    job = get_job_record(job_id)

    if not job:
        return False

    return job["status"] in {
        "SUCCEEDED",
        "FAILED",
    }
