from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageBackend(ABC):
    """
    Common interface for object storage.

    Application code should depend on this interface instead of directly
    writing files to the local filesystem.
    """

    @abstractmethod
    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        """
        Upload a file-like object and return the stored object key.
        """
        raise NotImplementedError

    @abstractmethod
    def download_fileobj(
        self,
        object_key: str,
        destination: BinaryIO,
    ) -> None:
        """
        Download an object into a writable file-like object.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, object_key: str) -> None:
        """
        Delete one stored object.
        """
        raise NotImplementedError

    @abstractmethod
    def object_exists(self, object_key: str) -> bool:
        """
        Return True if the object exists.
        """
        raise NotImplementedError