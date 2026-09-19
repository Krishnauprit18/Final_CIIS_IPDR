
from app.main import app
from app.core.config import DATASET_FILE, PROJECT_ROOT


_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _public_openapi_routes():
    """Return the public HTTP method/path contract from FastAPI's OpenAPI schema.

    This deliberately avoids inspecting FastAPI/Starlette private route wrapper
    internals. Different FastAPI versions may represent included routers
    differently in ``app.routes``, while the generated OpenAPI document is the
    stable public API contract consumed by clients.
    """
    schema = app.openapi()
    routes = set()
    for path, operations in schema.get("paths", {}).items():
        for method in operations:
            method_lower = method.lower()
            if method_lower in _HTTP_METHODS and method_lower not in {"head", "options"}:
                routes.add((method_lower.upper(), path))
    return routes


def test_phase1_route_contract_is_preserved():
    """All Phase 1 routes must remain available; later phases may add routes."""
    application_routes = _public_openapi_routes()

    route_snapshot = PROJECT_ROOT / "docs" / "phase-1" / "routes-before.txt"
    expected = set()
    for raw_line in route_snapshot.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        method, remainder = raw_line.split(" ", 1)
        path = remainder.split(" -> ", 1)[0]
        expected.add((method, path))

    assert expected.issubset(application_routes)


def test_phase1_uses_stable_dataset_path():
    assert DATASET_FILE == PROJECT_ROOT / "Scenario A1-ARFF" / "synthetic.csv"
    assert DATASET_FILE.exists()


def test_backend_main_is_compatibility_entrypoint():
    source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert "from app.main import app" in source
    assert "@app." not in source
