from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import legacy_handlers as handlers
from app.auth import repository as auth_repository
from app.auth.dependencies import current_user
from app.auth.permissions import CASE_EDIT_ROLES, require_case_access, require_case_role
from app.db.repositories import (
    create_case_record,
    get_case_record,
    list_saved_search_records,
    save_search_record,
)

router = APIRouter(tags=["cases"])


class CreateCaseRequest(BaseModel):
    name: str
    notes: Optional[str] = None


class SaveSearchRequest(BaseModel):
    criteria_json: dict[str, Any]
    notes: Optional[str] = None


@router.post("/cases")
def create_case(payload: CreateCaseRequest, user: dict = Depends(current_user)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Case name is required")

    case_id = create_case_record(name, user["username"])
    auth_repository.add_case_membership(
        case_id=case_id,
        user_id=int(user["id"]),
        role="OWNER",
    )
    auth_repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="case_created",
        outcome="success",
        resource_type="case",
        resource_id=str(case_id),
    )
    return {"id": case_id, "name": name}


@router.get("/cases")
def list_cases(user: dict = Depends(current_user)):
    rows = auth_repository.list_accessible_cases(
        int(user["id"]),
        is_admin="ADMIN" in set(user.get("roles") or []),
    )
    return {"cases": rows}


@router.post("/cases/{case_id}/save-search")
def save_search_to_case(
    case_id: int,
    payload: SaveSearchRequest,
    user: dict = Depends(current_user),
):
    if get_case_record(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_role(user, case_id, CASE_EDIT_ROLES)

    search_id = save_search_record(case_id, payload.criteria_json, payload.notes)
    auth_repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="saved_search_created",
        outcome="success",
        resource_type="case",
        resource_id=str(case_id),
        metadata={"saved_search_id": search_id},
    )
    return {"success": True, "id": search_id}


@router.get("/cases/{case_id}/searches")
def list_saved_searches(case_id: int, user: dict = Depends(current_user)):
    if get_case_record(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_access(user, case_id)
    return {"saved_searches": list_saved_search_records(case_id)}


@router.post("/cases/{case_id}/export-pack")
def export_case_pack(case_id: int, user: dict = Depends(current_user)):
    if get_case_record(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_access(user, case_id)
    auth_repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="case_export",
        outcome="success",
        resource_type="case",
        resource_id=str(case_id),
    )
    return handlers.export_case_pack(case_id, session={"username": user["username"]})


@router.post("/cases/{case_id}/ai-analyze")
async def ai_analyze_case(
    case_id: int,
    case_file: UploadFile = File(...),
    dataset_file: UploadFile = File(...),
    chunksize: Optional[int] = None,
    user: dict = Depends(current_user),
):
    if get_case_record(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_role(user, case_id, CASE_EDIT_ROLES)
    auth_repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="analysis_submitted",
        outcome="success",
        resource_type="case",
        resource_id=str(case_id),
    )
    return await handlers.ai_analyze_case(
        case_id=case_id,
        case_file=case_file,
        dataset_file=dataset_file,
        chunksize=chunksize,
    )
