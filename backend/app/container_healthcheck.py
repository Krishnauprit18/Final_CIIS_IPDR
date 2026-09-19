from __future__ import annotations

import os
import sys
import urllib.request


def _check(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return 0 if 200 <= response.status < 400 else 1
    except Exception:
        return 1


def main() -> int:
    role = os.getenv("CIIS_ROLE", "api").strip().lower()

    if role == "worker":
        port = int(os.getenv("WORKER_HEALTH_PORT", "9102"))
        return _check(f"http://127.0.0.1:{port}/health/live")

    return _check("http://127.0.0.1:8000/health/live")


if __name__ == "__main__":
    sys.exit(main())
