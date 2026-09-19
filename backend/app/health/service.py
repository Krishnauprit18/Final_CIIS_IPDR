from __future__ import annotations

from sqlalchemy import text

from app.db.session import get_engine
from app.queue.sqs import queue_healthcheck
from app.storage.service import verify_storage


def database_healthcheck() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def readiness_status() -> tuple[bool, dict[str, str]]:
    checks: dict[str, str] = {}
    ready = True

    for name, check in (
        ("database", database_healthcheck),
        ("storage", verify_storage),
        ("queue", queue_healthcheck),
    ):
        try:
            check()
            checks[name] = "ok"
        except Exception as exc:
            ready = False
            checks[name] = f"error:{type(exc).__name__}"

    return ready, checks
