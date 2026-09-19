"""Process liveness and dependency readiness endpoints."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import legacy_handlers as handlers
from app.health.service import readiness_report

router = APIRouter(tags=["health"])

router.add_api_route('/', handlers.read_root, methods=['GET'], name='read_root')


@router.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok", "service": "ciis-api"}


@router.get("/health/ready", tags=["health"])
def ready():
    report = readiness_report()
    if report["status"] != "ready":
        return JSONResponse(status_code=503, content=report)
    return report
