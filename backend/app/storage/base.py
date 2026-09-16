from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """Common interface for durable object storage."""

    @abstractmethod
    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def download_fileobj(self, object_key: str, destination: BinaryIO) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, object_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def object_exists(self, object_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> None:
        """Raise when the configured storage service/bucket is unavailable."""
        raise NotImplementedError
