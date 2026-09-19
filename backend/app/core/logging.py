from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.context import case_id_var, job_id_var, request_id_var


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": os.getenv("CIIS_ROLE", "api"),
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in (
            ("request_id", request_id_var.get()),
            ("job_id", job_id_var.get()),
            ("case_id", case_id_var.get()),
        ):
            if value is not None:
                payload[key] = value

        event = getattr(record, "event", None)
        if event:
            payload["event"] = event

        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
