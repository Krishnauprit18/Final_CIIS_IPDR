from __future__ import annotations

from contextvars import ContextVar
from typing import Optional


request_id_context: ContextVar[Optional[str]] = ContextVar(
    "ciis_request_id",
    default=None,
)
job_id_context: ContextVar[Optional[str]] = ContextVar(
    "ciis_job_id",
    default=None,
)
case_id_context: ContextVar[Optional[str]] = ContextVar(
    "ciis_case_id",
    default=None,
)


def context_values() -> dict[str, Optional[str]]:
    return {
        "request_id": request_id_context.get(),
        "job_id": job_id_context.get(),
        "case_id": case_id_context.get(),
    }
