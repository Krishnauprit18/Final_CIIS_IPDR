from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth import repository as auth_repository
from app.auth.dependencies import current_user
from app.auth.permissions import CASE_EDIT_ROLES, require_case_access, require_case_role
from app.core.context import request_id_var
from app.db.repositories import get_case_record
from app.metrics import FILES_UPLOADED_TOTAL
from app.jobs.service import (
    create_analysis_job,
    get_job,
    mark_job_failed,
)
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
    user: dict = Depends(current_user),
):
    case = get_case_record(case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    require_case_role(user, case_id, CASE_EDIT_ROLES)

    if not dataset_file.filename:
        raise HTTPException(
            status_code=400,
            detail="Dataset file is required",
        )

    request_id = request_id_var.get() or uuid.uuid4().hex
    dataset_key = (
        f"analysis-inputs/{case_id}/{request_id}/"
        f"{dataset_file.filename}"
    )

    upload_fileobj(
        dataset_file.file,
        dataset_key,
        content_type=dataset_file.content_type,
    )
    FILES_UPLOADED_TOTAL.inc()

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
        FILES_UPLOADED_TOTAL.inc()

    job = create_analysis_job(
        case_id=case_id,
        dataset_key=dataset_key,
        case_file_key=case_file_key,
        request_id=request_id,
    )

    try:
        send_analysis_message(
            {
                "job_id": job["id"],
                "case_id": case_id,
                "dataset_key": dataset_key,
                "case_file_key": case_file_key,
                "request_id": request_id,
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

    auth_repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="analysis_submitted",
        outcome="success",
        resource_type="case",
        resource_id=str(case_id),
        metadata={"job_id": job["id"]},
    )

    return {
        "job_id": job["id"],
        "status": "queued",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, user: dict = Depends(current_user)):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    case_id = job.get("case_id")
    if case_id is not None:
        require_case_access(user, int(case_id))

    return job
