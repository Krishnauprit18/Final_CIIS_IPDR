from __future__ import annotations

from typing import Callable

from sqlalchemy import text

from app.db.repositories import verify_database_schema
from app.db.session import get_engine
from app.queue.sqs import queue_healthcheck
from app.storage.service import verify_storage


def check_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    verify_database_schema()


def check_storage() -> None:
    verify_storage()


def check_queue() -> None:
    queue_healthcheck()


def _run_check(check: Callable[[], None]) -> dict[str, str]:
    try:
        check()
        return {"status": "ok"}
    except Exception as exc:
        # Do not return exception messages: SQLAlchemy/boto error text can
        # contain connection URLs or endpoint details that are not health data.
        return {"status": "error", "error": type(exc).__name__}


def readiness_report() -> dict:
    checks = {
        "database": _run_check(check_database),
        "storage": _run_check(check_storage),
        "queue": _run_check(check_queue),
    }
    ready = all(result["status"] == "ok" for result in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "service": "ciis-api",
        "checks": checks,
    }
