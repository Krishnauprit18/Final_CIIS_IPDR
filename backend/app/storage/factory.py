from __future__ import annotations

from functools import lru_cache

from app.core.config import (
    STORAGE_ACCESS_KEY,
    STORAGE_BUCKET,
    STORAGE_ENDPOINT_URL,
    STORAGE_REGION,
    STORAGE_SECRET_KEY,
    STORAGE_USE_SSL,
)
from app.storage.base import StorageBackend
from app.storage.s3 import S3StorageBackend


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Build the configured durable object-storage backend once per process."""
    return S3StorageBackend(
        bucket_name=STORAGE_BUCKET,
        endpoint_url=STORAGE_ENDPOINT_URL,
        access_key=STORAGE_ACCESS_KEY,
        secret_key=STORAGE_SECRET_KEY,
        region_name=STORAGE_REGION,
        use_ssl=STORAGE_USE_SSL,
    )
