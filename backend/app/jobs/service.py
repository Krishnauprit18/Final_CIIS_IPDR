from __future__ import annotations

import json
from typing import Any

from app.db.repositories import (
    claim_job,
    complete_claimed_job,
    create_job_record,
    fail_claimed_job,
    get_job_record,
    release_claim_for_retry,
    update_claimed_job_progress,
    update_job_status,
)


def create_analysis_job(
    *,
    case_id: int,
    dataset_key: str,
    case_file_key: str | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "case_id": case_id,
        "dataset_key": dataset_key,
        "case_file_key": case_file_key,
        "request_id": request_id,
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


def claim_analysis_job(job_id: int, worker_id: str, *, lease_seconds: int) -> dict[str, Any] | None:
    return claim_job(job_id, worker_id, lease_seconds=lease_seconds)


def set_job_progress(job_id: int, worker_id: str, progress: int) -> bool:
    return update_claimed_job_progress(job_id, worker_id, progress)


def complete_job(job_id: int, worker_id: str, result_uri: str) -> bool:
    return complete_claimed_job(job_id, worker_id, result_uri)


def retry_job(job_id: int, worker_id: str, error: str) -> bool:
    return release_claim_for_retry(job_id, worker_id, error)


def fail_job(job_id: int, worker_id: str, error: str) -> bool:
    return fail_claimed_job(job_id, worker_id, error)


def mark_job_failed(job_id: int, error: str) -> None:
    """Used when queue publication fails before any worker has claimed the job."""
    update_job_status(job_id, "FAILED", error_message=error[:2000])


def job_is_terminal(job_id: int) -> bool:
    job = get_job_record(job_id)
    return bool(job and job["status"] in {"SUCCEEDED", "FAILED"})
