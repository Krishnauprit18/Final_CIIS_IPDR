from __future__ import annotations

from functools import lru_cache

import boto3

from app.core.config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    SECRETS_MANAGER_ENDPOINT_URL,
)


@lru_cache(maxsize=1)
def get_secrets_client():
    return boto3.client(
        "secretsmanager",
        endpoint_url=SECRETS_MANAGER_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
