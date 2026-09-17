from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import delete, select, text, update

from app.db.models import AuditLog, AuthSession, Case, Job, SavedSearch, User
from app.db.session import get_engine, session_scope

EXPECTED_ALEMBIC_REVISION = "0002_phase5_job_correctness"


def _model_to_dict(instance: Any) -> Dict[str, Any]:
    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}


def verify_database_schema() -> None:
    """Fail fast unless PostgreSQL is reachable and Alembic migration is current."""
    with get_engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if revision != EXPECTED_ALEMBIC_REVISION:
            raise RuntimeError(
                f"Database schema is not current: expected {EXPECTED_ALEMBIC_REVISION!r}, got {revision!r}. "
                "Run `alembic upgrade head` before starting the API."
            )


def log_action(username: Optional[str], action: str, details: str = "") -> None:
    try:
        with session_scope() as db:
            db.add(AuditLog(
                username=username,
                action=action,
                details=(details or "")[:1000],
                created_at=datetime.now(),
            ))
    except Exception:
        pass


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        user = db.scalar(select(User).where(User.username == username))
        return _model_to_dict(user) if user else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        return _model_to_dict(user) if user else None


def insert_user(user: Dict[str, Any]) -> None:
    profile = user.get("profile", {})
    created_at = user.get("created_at", datetime.now())
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    with session_scope() as db:
        db.add(User(
            username=user["username"],
            email=user.get("email"),
            password_hash=user["password_hash"],
            password_salt=user.get("password_salt"),
            name=user.get("name"),
            post=profile.get("post"),
            district=profile.get("district"),
            thana=profile.get("thana"),
            created_at=created_at,
        ))


def update_user_fields(username: str, updates: Dict[str, Any]) -> None:
    allowed = {"name", "post", "district", "thana"}
    values = {key: value for key, value in updates.items() if key in allowed}
    if not values:
        return
    with session_scope() as db:
        db.execute(update(User).where(User.username == username).values(**values))


def update_user_password(username: str, password_hash: str, password_salt: str) -> None:
    with session_scope() as db:
        db.execute(
            update(User)
            .where(User.username == username)
            .values(password_hash=password_hash, password_salt=password_salt)
        )


def create_session(token: str, username: str, expires_at: datetime) -> None:
    with session_scope() as db:
        db.add(AuthSession(
            token=token,
            username=username,
            created_at=datetime.now(),
            expires_at=expires_at,
        ))


def get_session(token: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.token == token))
        return _model_to_dict(session) if session else None


def delete_session(token: str) -> None:
    with session_scope() as db:
        db.execute(delete(AuthSession).where(AuthSession.token == token))


def delete_sessions_for_username(username: str) -> None:
    with session_scope() as db:
        db.execute(delete(AuthSession).where(AuthSession.username == username))


def create_case_record(name: str, created_by: Optional[str]) -> int:
    with session_scope() as db:
        case = Case(name=name, created_by=created_by, created_at=datetime.now())
        db.add(case)
        db.flush()
        return case.id


def list_case_records() -> list[Dict[str, Any]]:
    with session_scope() as db:
        rows = db.scalars(select(Case).order_by(Case.id.desc())).all()
        return [_model_to_dict(row) for row in rows]


def get_case_record(case_id: int) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        case = db.get(Case, case_id)
        return _model_to_dict(case) if case else None


def save_search_record(case_id: int, criteria: Dict[str, Any], notes: Optional[str]) -> int:
    with session_scope() as db:
        if db.get(Case, case_id) is None:
            raise KeyError(case_id)
        record = SavedSearch(
            case_id=case_id,
            criteria_json=json.dumps(criteria),
            notes=notes or "",
            created_at=datetime.now(),
        )
        db.add(record)
        db.flush()
        return record.id


def list_saved_search_records(case_id: int) -> list[Dict[str, Any]]:
    with session_scope() as db:
        rows = db.scalars(
            select(SavedSearch)
            .where(SavedSearch.case_id == case_id)
            .order_by(SavedSearch.id.desc())
        ).all()
        return [_model_to_dict(row) for row in rows]


def create_job_record(*, case_id: int, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    with session_scope() as db:
        job = Job(
            case_id=case_id,
            job_type=job_type,
            status="QUEUED",
            payload_json=json.dumps(payload),
            error_message=None,
            progress=0,
            attempt_count=0,
            worker_id=None,
            claim_expires_at=None,
            started_at=None,
            finished_at=None,
            result_uri=None,
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        db.flush()
        return _model_to_dict(job)


def get_job_record(job_id: int) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        job = db.get(Job, job_id)
        return _model_to_dict(job) if job else None


def claim_job(job_id: int, worker_id: str, *, lease_seconds: int) -> Optional[Dict[str, Any]]:
    """Atomically claim queued work or recover an expired RUNNING lease.

    PostgreSQL row locking serializes competing workers for the same job. A
    RUNNING job with a live lease is owned by another worker and is not claimed.
    SUCCEEDED/FAILED jobs are returned unchanged so the caller can handle an
    at-least-once duplicate message without doing the analysis twice.
    """
    now = datetime.now()
    with session_scope() as db:
        job = db.scalar(
            select(Job)
            .where(Job.id == job_id)
            .with_for_update()
        )
        if job is None:
            return None

        if job.status in {"SUCCEEDED", "FAILED"}:
            return _model_to_dict(job)

        if (
            job.status == "RUNNING"
            and job.claim_expires_at is not None
            and job.claim_expires_at > now
            and job.worker_id != worker_id
        ):
            return None

        job.status = "RUNNING"
        job.worker_id = worker_id
        job.claim_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempt_count = int(job.attempt_count or 0) + 1
        job.progress = max(int(job.progress or 0), 1)
        job.error_message = None
        job.started_at = job.started_at or now
        job.updated_at = now
        db.flush()
        return _model_to_dict(job)


def update_claimed_job_progress(job_id: int, worker_id: str, progress: int) -> bool:
    progress = max(0, min(100, int(progress)))
    with session_scope() as db:
        result = db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "RUNNING",
                Job.worker_id == worker_id,
            )
            .values(progress=progress, updated_at=datetime.now())
        )
        return bool(result.rowcount)


def complete_claimed_job(job_id: int, worker_id: str, result_uri: str) -> bool:
    now = datetime.now()
    with session_scope() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            return False
        if job.status == "SUCCEEDED":
            return True
        if job.status != "RUNNING" or job.worker_id != worker_id:
            return False

        job.status = "SUCCEEDED"
        job.progress = 100
        job.result_uri = result_uri
        job.error_message = None
        job.finished_at = now
        job.worker_id = None
        job.claim_expires_at = None
        job.updated_at = now
        return True


def release_claim_for_retry(job_id: int, worker_id: str, error_message: str) -> bool:
    now = datetime.now()
    with session_scope() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.status != "RUNNING" or job.worker_id != worker_id:
            return False
        job.status = "QUEUED"
        job.error_message = error_message[:2000]
        job.worker_id = None
        job.claim_expires_at = None
        job.updated_at = now
        return True


def fail_claimed_job(job_id: int, worker_id: str, error_message: str) -> bool:
    now = datetime.now()
    with session_scope() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            return False
        if job.status == "FAILED":
            return True
        if job.status != "RUNNING" or job.worker_id != worker_id:
            return False
        job.status = "FAILED"
        job.error_message = error_message[:2000]
        job.finished_at = now
        job.worker_id = None
        job.claim_expires_at = None
        job.updated_at = now
        return True


def update_job_status(job_id: int, status: str, *, error_message: Optional[str] = None) -> None:
    with session_scope() as db:
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=status, error_message=error_message, updated_at=datetime.now())
        )


def update_job_payload(job_id: int, payload: Dict[str, Any]) -> None:
    with session_scope() as db:
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(payload_json=json.dumps(payload), updated_at=datetime.now())
        )
