from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.core.config import STORAGE_BUCKET, STORAGE_ENDPOINT_URL
from app.storage.base import StorageBackend
from app.storage import service


class MemoryStorage(StorageBackend):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_fileobj(self, fileobj, object_key: str, content_type: str | None = None) -> str:
        self.objects[object_key] = fileobj.read()
        return object_key

    def download_fileobj(self, object_key: str, destination) -> None:
        destination.write(self.objects[object_key])

    def delete_object(self, object_key: str) -> None:
        self.objects.pop(object_key, None)

    def object_exists(self, object_key: str) -> bool:
        return object_key in self.objects

    def healthcheck(self) -> None:
        return None


def test_phase3_defaults_target_local_minio():
    assert STORAGE_BUCKET == "ciis-storage"
    assert STORAGE_ENDPOINT_URL == "http://localhost:9000"


def test_phase3_storage_service_round_trip(monkeypatch):
    backend = MemoryStorage()
    monkeypatch.setattr(service, "get_storage_backend", lambda: backend)

    uri = service.upload_bytes(b"hello", "tests/hello.txt", content_type="text/plain")
    assert uri == "s3://ciis-storage/tests/hello.txt"
    assert service.object_exists("tests/hello.txt") is True
    assert service.download_bytes("tests/hello.txt") == b"hello"

    service.delete_object("tests/hello.txt")
    assert service.object_exists("tests/hello.txt") is False


def test_phase3_main_installs_storage_before_router_imports():
    source = (Path(__file__).parent / "app" / "main.py").read_text(encoding="utf-8")
    install_at = source.index("install_legacy_object_storage_compat(legacy_handlers)")
    routers_at = source.index("from app.api.routers import")
    assert install_at < routers_at
    health = (
        Path(__file__).parent / "app" / "health" / "service.py"
    ).read_text(encoding="utf-8")
    assert "verify_storage" in health


def test_phase3_minio_compose_bootstraps_private_bucket():
    compose = (Path(__file__).parent.parent / "compose.storage.yaml").read_text(encoding="utf-8")
    assert "quay.io/minio/minio:latest" in compose
    assert "quay.io/minio/mc:latest" in compose
    assert "mc mb --ignore-existing local/ciis-storage" in compose
    assert "mc anonymous set none local/ciis-storage" in compose
