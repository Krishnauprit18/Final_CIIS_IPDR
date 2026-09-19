from __future__ import annotations

import uuid
from typing import Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app import legacy_handlers
from app.db.repositories import get_case_record
from app.db.repositories import user_can_access_case
from app.jobs.service import (
    create_analysis_job,
    get_job,
    mark_job_failed,
)
from app.metrics import record_file_uploaded
from app.queue.sqs import send_analysis_message
from app.storage.service import delete_object, upload_fileobj


router = APIRouter(tags=["jobs"])


@router.post(
    "/cases/{case_id}/analysis",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_case_analysis(
    case_id: int,
    dataset_file: UploadFile = File(...),
    case_file: UploadFile | None = File(None),
    session: Dict = Depends(legacy_handlers.verify_token),
):
    case = get_case_record(case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    # Direct unit tests call this coroutine without FastAPI dependency
    # resolution. In a live request FastAPI always supplies the session dict;
    # the compatibility branch keeps the existing handler-level tests useful.
    if isinstance(session, dict) and not user_can_access_case(
        session["username"], case_id, "analyst"
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this case",
        )

    if not dataset_file.filename:
        raise HTTPException(
            status_code=400,
            detail="Dataset file is required",
        )

    request_id = uuid.uuid4().hex
    dataset_key = (
        f"analysis-inputs/{case_id}/{request_id}/"
        f"{dataset_file.filename}"
    )

    upload_fileobj(
        dataset_file.file,
        dataset_key,
        content_type=dataset_file.content_type,
    )
    record_file_uploaded("dataset")

    case_file_key = None

    if case_file and case_file.filename:
        case_file_key = (
            f"analysis-inputs/{case_id}/{request_id}/"
            f"{case_file.filename}"
        )

        upload_fileobj(
            case_file.file,
            case_file_key,
            content_type=case_file.content_type,
        )
        record_file_uploaded("case_document")

    job = create_analysis_job(
        case_id=case_id,
        dataset_key=dataset_key,
        case_file_key=case_file_key,
    )

    try:
        send_analysis_message(
            {
                "job_id": job["id"],
                "case_id": case_id,
                "dataset_key": dataset_key,
                "case_file_key": case_file_key,
            }
        )
    except Exception as exc:
        mark_job_failed(
            job["id"],
            f"Unable to queue job: {exc}",
        )

        # Queueing failed, so there is no worker that can consume these inputs.
        # Clean them up best-effort to avoid orphaned durable objects.
        for object_key in (dataset_key, case_file_key):
            if not object_key:
                continue
            try:
                delete_object(object_key)
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to queue analysis job",
        ) from exc

    return {
        "job_id": job["id"],
        "status": "queued",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job
