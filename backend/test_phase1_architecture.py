from pathlib import Path

from app.main import app
from app.core.config import DATASET_FILE, PROJECT_ROOT


def _iter_registered_routes(routes):
    """Yield concrete FastAPI routes across direct and included-router wrappers."""
    for route in routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)

        if path is not None and methods:
            yield route

        nested_routes = getattr(route, "routes", None)
        if nested_routes:
            yield from _iter_registered_routes(nested_routes)
            continue

        nested_router = getattr(route, "router", None)
        nested_router_routes = getattr(nested_router, "routes", None)
        if nested_router_routes:
            yield from _iter_registered_routes(nested_router_routes)


def test_phase1_route_contract_is_preserved():
    application_routes = {
        (method, route.path)
        for route in _iter_registered_routes(app.routes)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
        and route.path not in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    }

    route_snapshot = PROJECT_ROOT / "docs" / "phase-1" / "routes-before.txt"
    expected = set()
    for raw_line in route_snapshot.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        method, remainder = raw_line.split(" ", 1)
        path = remainder.split(" -> ", 1)[0]
        expected.add((method, path))

    assert application_routes == expected


def test_phase1_uses_stable_dataset_path():
    assert DATASET_FILE == PROJECT_ROOT / "Scenario A1-ARFF" / "synthetic.csv"
    assert DATASET_FILE.exists()


def test_backend_main_is_compatibility_entrypoint():
    source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "from app.main import app" in source
    assert "@app." not in source
