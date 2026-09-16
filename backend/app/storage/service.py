from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from app.core.config import STORAGE_BUCKET
from app.storage.factory import get_storage_backend


def normalize_object_key(object_key: str) -> str:
    key = object_key.replace("\\", "/").lstrip("/")
    if not key or key.endswith("/"):
        raise ValueError("object_key must identify an object, not a bucket/prefix")
    return key


def storage_uri(object_key: str) -> str:
    return f"s3://{STORAGE_BUCKET}/{normalize_object_key(object_key)}"


def upload_fileobj(
    fileobj: BinaryIO,
    object_key: str,
    content_type: str | None = None,
) -> str:
    key = normalize_object_key(object_key)
    get_storage_backend().upload_fileobj(fileobj, key, content_type=content_type)
    return storage_uri(key)


def upload_bytes(data: bytes, object_key: str, content_type: str | None = None) -> str:
    return upload_fileobj(BytesIO(data), object_key, content_type=content_type)


def upload_path(
    path: str | Path,
    object_key: str,
    *,
    content_type: str | None = None,
    delete_local: bool = False,
) -> str:
    local_path = Path(path)
    with local_path.open("rb") as handle:
        uri = upload_fileobj(handle, object_key, content_type=content_type)
    if delete_local:
        local_path.unlink(missing_ok=True)
    return uri


def download_bytes(object_key: str) -> bytes:
    destination = BytesIO()
    get_storage_backend().download_fileobj(normalize_object_key(object_key), destination)
    return destination.getvalue()


def object_exists(object_key: str) -> bool:
    return get_storage_backend().object_exists(normalize_object_key(object_key))


def delete_object(object_key: str) -> None:
    get_storage_backend().delete_object(normalize_object_key(object_key))


def verify_storage() -> None:
    get_storage_backend().healthcheck()
