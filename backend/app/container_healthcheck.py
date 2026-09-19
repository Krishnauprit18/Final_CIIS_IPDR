from __future__ import annotations

import os
import sys
import urllib.request

from app.workers.health import worker_healthcheck


def main() -> int:
    role = os.getenv("CIIS_ROLE", "api").strip().lower()

    if role == "worker":
        return 0 if worker_healthcheck() else 1

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=3) as response:
            return 0 if 200 <= response.status < 400 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
