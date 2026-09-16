from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"
CONFIG_FILE = BACKEND_DIR / "config.yml"
DATASET_FILE = PROJECT_ROOT / "Scenario A1-ARFF" / "synthetic.csv"
UPLOAD_DIR = BACKEND_DIR / "uploads"

def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except OSError:
        pass

load_env_file()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
