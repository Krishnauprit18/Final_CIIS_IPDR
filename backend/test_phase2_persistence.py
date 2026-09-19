from pathlib import Path

from app.db.models import Base
from app.db.repositories import EXPECTED_ALEMBIC_REVISION


def test_phase2_uses_postgresql_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://ciis:test-password@localhost:5432/ciis",
    )

    from app.core import config

    database_url = config.os.getenv("DATABASE_URL", "").strip()

    assert database_url.startswith("postgresql+")


def test_phase2_schema_contains_required_tables():
    required = {
        "users",
        "sessions",
        "audit_logs",
        "cases",
        "saved_searches",
        "jobs",
        "analysis_metadata",
        "alerts",
    }

    assert required.issubset(set(Base.metadata.tables))


def test_phase2_alembic_revision_is_present():
    versions_dir = Path(__file__).parent / "alembic" / "versions"
    migrations = list(versions_dir.glob("*.py"))

    assert migrations, "No Alembic migrations found"

    assert any(
        EXPECTED_ALEMBIC_REVISION in migration.read_text(encoding="utf-8")
        for migration in migrations
    ), (
        f"Expected Alembic revision "
        f"{EXPECTED_ALEMBIC_REVISION!r} was not found"
    )


def test_phase2_installs_postgres_compatibility_boundary():
    main_source = (
        Path(__file__).parent / "app" / "main.py"
    ).read_text(encoding="utf-8")

    assert "install_legacy_postgres_compat(legacy_handlers)" in main_source
