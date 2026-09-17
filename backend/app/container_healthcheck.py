from __future__ import annotations

import os
import sys
import urllib.request


def main() -> int:
    role = os.getenv("CIIS_ROLE", "api").strip().lower()

    if role == "worker":
        # Docker runs the healthcheck as a child process inside the worker
        # container. If this module can execute, the container runtime is alive;
        # the worker process itself is PID 1 and Docker will stop the container if
        # that process exits.
        return 0

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3) as response:
            return 0 if 200 <= response.status < 400 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
