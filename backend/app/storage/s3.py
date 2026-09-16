from __future__ import annotations

from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    def __init__(
        self,
        *,
        bucket_name: str,
        endpoint_url: str | None,
        access_key: str | None,
        secret_key: str | None,
        region_name: str = "us-east-1",
        use_ssl: bool = False,
    ) -> None:
        self.bucket_name = bucket_name

        client_kwargs = {
            "endpoint_url": endpoint_url,
            "region_name": region_name,
            "use_ssl": use_ssl,
            "config": Config(signature_version="s3v4"),
        }
        if access_key:
            client_kwargs["aws_access_key_id"] = access_key
        if secret_key:
            client_kwargs["aws_secret_access_key"] = secret_key

        self.client = boto3.client("s3", **client_kwargs)

    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        object_key: str,
        content_type: str | None = None,
    ) -> str:
        kwargs = {}
        if content_type:
            kwargs["ExtraArgs"] = {"ContentType": content_type}

        self.client.upload_fileobj(
            fileobj,
            self.bucket_name,
            object_key,
            **kwargs,
        )
        return object_key

    def download_fileobj(self, object_key: str, destination: BinaryIO) -> None:
        self.client.download_fileobj(self.bucket_name, object_key, destination)

    def delete_object(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket_name, Key=object_key)

    def object_exists(self, object_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def healthcheck(self) -> None:
        self.client.head_bucket(Bucket=self.bucket_name)
