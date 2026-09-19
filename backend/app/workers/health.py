from __future__ import annotations

import os
import time
from pathlib import Path


HEARTBEAT_FILE = Path(
    os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/ciis-worker-heartbeat")
)
HEARTBEAT_MAX_AGE_SECONDS = float(
    os.getenv("WORKER_HEARTBEAT_MAX_AGE_SECONDS", "90")
)


def touch_worker_heartbeat() -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()


def worker_healthcheck() -> bool:
    try:
        age = time.time() - HEARTBEAT_FILE.stat().st_mtime
        return 0 <= age <= HEARTBEAT_MAX_AGE_SECONDS
    except (FileNotFoundError, OSError):
        return False
