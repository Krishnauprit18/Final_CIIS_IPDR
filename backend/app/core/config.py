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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


load_env_file()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://ciis:ciis@localhost:5432/ciis",
)

# Phase 3 object storage. The defaults target the local MinIO service; in
# production, STORAGE_ENDPOINT_URL may be left empty so boto3 uses AWS S3.
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "ciis-storage")
STORAGE_ENDPOINT_URL = os.getenv("STORAGE_ENDPOINT_URL", "http://localhost:9000").strip() or None
STORAGE_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "ciisadmin").strip() or None
STORAGE_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "ciisadmin123").strip() or None
STORAGE_REGION = os.getenv("STORAGE_REGION", "us-east-1")
STORAGE_USE_SSL = _env_bool("STORAGE_USE_SSL", default=False)

# Phase 4 queue configuration. Local development points at LocalStack. In AWS,
# leave SQS_ENDPOINT_URL / explicit keys empty and boto3 will use the standard
# AWS credential provider chain (for example an EC2/ECS/IAM role).
SQS_ENDPOINT_URL = os.getenv(
    "SQS_ENDPOINT_URL",
    "http://localhost:4566",
).strip() or None

SQS_REGION = os.getenv(
    "SQS_REGION",
    "us-east-1",
)

SQS_ACCESS_KEY = os.getenv(
    "SQS_ACCESS_KEY",
    "test",
).strip() or None

SQS_SECRET_KEY = os.getenv(
    "SQS_SECRET_KEY",
    "test",
).strip() or None

SQS_ANALYSIS_QUEUE_NAME = os.getenv(
    "SQS_ANALYSIS_QUEUE_NAME",
    "ciis-analysis",
)

SQS_ANALYSIS_DLQ_NAME = os.getenv(
    "SQS_ANALYSIS_DLQ_NAME",
    "ciis-analysis-dlq",
)

WORKER_POLL_SECONDS = int(
    os.getenv("WORKER_POLL_SECONDS", "20")
)

WORKER_VISIBILITY_TIMEOUT = int(
    os.getenv("WORKER_VISIBILITY_TIMEOUT", "900")
)
