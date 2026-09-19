from __future__ import annotations

import re
import uuid

from fastapi import Request

from app.core.context import request_id_var
from app.core.logging import get_logger

logger = get_logger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


async def request_context_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "").strip()
    request_id = (
        incoming
        if incoming and _REQUEST_ID_PATTERN.fullmatch(incoming)
        else uuid.uuid4().hex
    )
    token = request_id_var.set(request_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={"event": "http_request_completed"},
        )
        return response
    finally:
        request_id_var.reset(token)
