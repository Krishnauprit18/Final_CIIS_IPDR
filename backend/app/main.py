from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import legacy_handlers
from app.core.config import FRONTEND_ORIGIN
from app.db.legacy_compat import install_legacy_postgres_compat
from app.metrics import metrics_endpoint, metrics_middleware
from app.queue.sqs import queue_healthcheck
from app.storage.legacy_compat import install_legacy_object_storage_compat
from app.storage.service import verify_storage

# Install runtime compatibility boundaries before routers capture handler
# callables. This preserves the public API while moving persistence to
# PostgreSQL (Phase 2) and durable file artifacts to object storage (Phase 3).
install_legacy_postgres_compat(legacy_handlers)
install_legacy_object_storage_compat(legacy_handlers)

from app.api.routers import (
    analysis,
    analytics,
    auth,
    cases,
    health,
    jobs,
    link_analysis,
    mapping,
    maps,
    normalization,
    processing,
    search,
)


def create_app() -> FastAPI:
    application = FastAPI(title="CIIS IPDR Analysis API")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[FRONTEND_ORIGIN],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.middleware("http")(metrics_middleware)

    application.add_api_route(
        "/metrics",
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )

    application.include_router(analysis.router)
    application.include_router(analytics.router)
    application.include_router(auth.router)
    application.include_router(cases.router)
    application.include_router(health.router)
    application.include_router(jobs.router)
    application.include_router(link_analysis.router)
    application.include_router(mapping.router)
    application.include_router(maps.router)
    application.include_router(normalization.router)
    application.include_router(processing.router)
    application.include_router(search.router)

    @application.on_event("startup")
    def _startup() -> None:
        legacy_handlers.startup_event()
        verify_storage()
        queue_healthcheck()

    return application


app = create_app()
startup_event = legacy_handlers.startup_event
