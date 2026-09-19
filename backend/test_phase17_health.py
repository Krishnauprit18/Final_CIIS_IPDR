from pathlib import Path

from fastapi.responses import JSONResponse

from app.api.routers import health
from app.workers import health as worker_health


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_liveness_does_not_require_dependencies():
    assert health.live() == {"status": "ok", "service": "ciis-api"}


def test_readiness_returns_503_when_a_dependency_is_down(monkeypatch):
    monkeypatch.setattr(
        health,
        "readiness_report",
        lambda: {
            "status": "not_ready",
            "service": "ciis-api",
            "checks": {"database": {"status": "error", "error": "TimeoutError"}},
        },
    )

    response = health.ready()

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503


def test_worker_heartbeat_healthcheck(monkeypatch, tmp_path):
    heartbeat = tmp_path / "worker-heartbeat"
    monkeypatch.setattr(worker_health, "HEARTBEAT_FILE", heartbeat)
    monkeypatch.setattr(worker_health, "HEARTBEAT_MAX_AGE_SECONDS", 90.0)

    assert not worker_health.worker_healthcheck()
    worker_health.touch_worker_heartbeat()
    assert worker_health.worker_healthcheck()


def test_phase17_probes_use_dedicated_endpoints_and_worker_exec_check():
    api = (
        PROJECT_ROOT
        / "deploy"
        / "helm"
        / "ciis"
        / "templates"
        / "api-deployment.yaml"
    ).read_text(encoding="utf-8")
    worker = (
        PROJECT_ROOT
        / "deploy"
        / "helm"
        / "ciis"
        / "templates"
        / "worker-deployment.yaml"
    ).read_text(encoding="utf-8")

    assert "path: /health/ready" in api
    assert "path: /health/live" in api
    assert '"app.container_healthcheck"' in worker
