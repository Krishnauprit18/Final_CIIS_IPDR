from pathlib import Path

from app.core.config import DATABASE_URL
from app.db.models import Base
from app.db.repositories import EXPECTED_ALEMBIC_REVISION


def test_phase2_uses_postgresql_database_url():
    assert DATABASE_URL.startswith("postgresql+")


def test_phase2_schema_contains_required_tables():
    required = {
        "users", "sessions", "audit_logs", "cases", "saved_searches",
        "jobs", "analysis_metadata", "alerts",
    }
    assert required.issubset(set(Base.metadata.tables))


def test_phase2_alembic_revision_is_present():
    migration = Path(__file__).parent / "alembic" / "versions" / "0001_initial_postgresql.py"
    assert migration.exists()
    assert EXPECTED_ALEMBIC_REVISION in migration.read_text(encoding="utf-8")


def test_phase2_installs_postgres_compatibility_boundary():
    main_source = (Path(__file__).parent / "app" / "main.py").read_text(encoding="utf-8")
    assert "install_legacy_postgres_compat(legacy_handlers)" in main_source
