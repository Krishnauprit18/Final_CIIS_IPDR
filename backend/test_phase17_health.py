from __future__ import annotations

import time

from app.api.routers import health as health_router
from app.health import service
from app.health import worker


def test_liveness_is_dependency_free():
    assert health_router.live() == {"status": "ok"}


def test_readiness_reports_all_dependencies(monkeypatch):
    monkeypatch.setattr(service, "database_healthcheck", lambda: None)
    monkeypatch.setattr(service, "verify_storage", lambda: None)
    monkeypatch.setattr(service, "queue_healthcheck", lambda: None)

    ready, checks = service.readiness_status()

    assert ready is True
    assert checks == {
        "database": "ok",
        "storage": "ok",
        "queue": "ok",
    }


def test_readiness_fails_without_killing_liveness(monkeypatch):
    def fail_database():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(service, "database_healthcheck", fail_database)
    monkeypatch.setattr(service, "verify_storage", lambda: None)
    monkeypatch.setattr(service, "queue_healthcheck", lambda: None)

    ready, checks = service.readiness_status()

    assert ready is False
    assert checks["database"] == "error:RuntimeError"
    assert health_router.live() == {"status": "ok"}


def test_worker_heartbeat_detects_stale_loop(monkeypatch):
    monkeypatch.setenv("WORKER_HEARTBEAT_TIMEOUT_SECONDS", "30")
    monkeypatch.setattr(worker, "_last_heartbeat", time.monotonic() - 31)

    alive, details = worker.worker_liveness()

    assert alive is False
    assert details["status"] == "stale"


def test_worker_heartbeat_recovers():
    worker.touch_worker_heartbeat()
    alive, details = worker.worker_liveness()
    assert alive is True
    assert details["status"] == "ok"
