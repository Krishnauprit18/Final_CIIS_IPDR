from __future__ import annotations

import json
from typing import Any

from app.secrets.client import get_secrets_client


def get_secret_json(secret_id: str) -> dict[str, Any]:
    response = get_secrets_client().get_secret_value(SecretId=secret_id)

    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError(f"Secret {secret_id!r} does not contain SecretString")

    parsed = json.loads(secret_string)

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Secret {secret_id!r} must contain a JSON object")

    return parsed
