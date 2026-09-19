from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.health.service import readiness_status

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {"message": "IPDR Analysis Backend is running."}


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    is_ready, dependencies = readiness_status()
    payload = {
        "status": "ready" if is_ready else "not_ready",
        "dependencies": dependencies,
    }
    if is_ready:
        return payload
    return JSONResponse(status_code=503, content=payload)
