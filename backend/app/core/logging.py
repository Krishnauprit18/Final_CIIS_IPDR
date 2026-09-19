from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.request_context import context_values


class JsonFormatter(logging.Formatter):
    """Small dependency-free JSON formatter safe for container log shipping."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{key: value for key, value in context_values().items() if value},
        }

        for key in ("event", "method", "path", "status", "duration_ms", "worker_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)

    formatter = JsonFormatter()
    for handler in root.handlers:
        handler.setFormatter(formatter)
