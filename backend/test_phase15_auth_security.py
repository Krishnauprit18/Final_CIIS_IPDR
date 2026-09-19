from pathlib import Path

from app.auth.security import hash_password, hash_session_token, verify_argon2_password
from app.db.models import Base
from app.db.repositories import EXPECTED_ALEMBIC_REVISION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_new_password_hashes_are_argon2id_and_verifiable():
    encoded = hash_password("phase15-test-password")

    assert encoded.startswith("$argon2id$")
    assert verify_argon2_password("phase15-test-password", encoded)
    assert not verify_argon2_password("wrong-password", encoded)


def test_bearer_token_persistence_uses_a_digest():
    raw = "opaque-token-that-must-not-be-stored"
    digest = hash_session_token(raw)

    assert digest != raw
    assert len(digest) == 64
    assert digest == hash_session_token(raw)


def test_case_membership_is_in_the_persistence_model():
    assert "case_memberships" in Base.metadata.tables
    columns = set(Base.metadata.tables["case_memberships"].columns.keys())
    assert {"user_id", "case_id", "role", "created_at"}.issubset(columns)


def test_phase15_migration_is_the_expected_schema_head():
    assert EXPECTED_ALEMBIC_REVISION == "0004_phase15_auth_rbac"
    security_migration = (
        PROJECT_ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "0003_phase15_auth_security.py"
    ).read_text(encoding="utf-8")
    rbac_migration = (
        PROJECT_ROOT
        / "backend"
        / "alembic"
        / "versions"
        / "0004_phase15_auth_rbac.py"
    ).read_text(encoding="utf-8")
    assert 'op.execute("DELETE FROM sessions")' in security_migration
    assert '"case_memberships"' in security_migration
    assert 'revision = "0004_phase15_auth_rbac"' in rbac_migration
    assert '"refresh_sessions"' in rbac_migration
    assert '"audit_events"' in rbac_migration


def test_case_and_job_routes_require_authenticated_access():
    cases = (
        PROJECT_ROOT / "backend" / "app" / "legacy_handlers.py"
    ).read_text(encoding="utf-8")
    jobs = (
        PROJECT_ROOT / "backend" / "app" / "api" / "routers" / "jobs.py"
    ).read_text(encoding="utf-8")

    assert "def _require_case_access" in cases
    assert "status_code=403" in cases
    assert "Depends(current_user)" in jobs
    assert "require_case_role" in jobs
