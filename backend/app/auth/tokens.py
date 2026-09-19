from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import ACCESS_TOKEN_MINUTES, AUTH_SECRET, REFRESH_TOKEN_DAYS

ALGORITHM = "HS256"


def _secret() -> str:
    if len(AUTH_SECRET) < 32:
        raise RuntimeError("AUTH_SECRET must be configured with at least 32 characters")
    return AUTH_SECRET


def create_access_token(*, user_id: int, username: str, roles: list[str]) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    return token, ACCESS_TOKEN_MINUTES * 60


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def create_refresh_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS)
    return raw, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
