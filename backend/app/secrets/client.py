from __future__ import annotations

import os
from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def get_secrets_client():
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "").strip() or None
    region_name = os.getenv("AWS_REGION", "us-east-1")

    return boto3.client(
        "secretsmanager",
        endpoint_url=endpoint_url,
        region_name=region_name,
    )
