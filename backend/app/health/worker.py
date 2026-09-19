from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.health.service import readiness_status

_last_heartbeat = time.monotonic()
_heartbeat_lock = threading.Lock()


def touch_worker_heartbeat() -> None:
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.monotonic()


def worker_liveness() -> tuple[bool, dict[str, object]]:
    threshold = max(
        30,
        int(os.getenv("WORKER_HEARTBEAT_TIMEOUT_SECONDS", "600")),
    )
    with _heartbeat_lock:
        age = time.monotonic() - _last_heartbeat

    return age <= threshold, {
        "status": "ok" if age <= threshold else "stale",
        "heartbeat_age_seconds": round(age, 3),
        "threshold_seconds": threshold,
    }


class _Handler(BaseHTTPRequestHandler):
    def _write(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health/live":
            alive, detail = worker_liveness()
            self._write(200 if alive else 500, detail)
            return

        if self.path == "/health/ready":
            ready, checks = readiness_status()
            self._write(
                200 if ready else 503,
                {
                    "status": "ready" if ready else "not_ready",
                    "dependencies": checks,
                },
            )
            return

        self._write(404, {"status": "not_found"})

    def log_message(self, format: str, *args) -> None:
        return


def start_worker_health_server() -> None:
    port = int(os.getenv("WORKER_HEALTH_PORT", "9102"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(
        target=server.serve_forever,
        name="ciis-worker-health",
        daemon=True,
    ).start()
