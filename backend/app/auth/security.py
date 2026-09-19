from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError


PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Return an Argon2id encoded password hash."""
    return PASSWORD_HASHER.hash(password)


def verify_argon2_password(password: str, encoded_hash: str) -> bool:
    try:
        return bool(PASSWORD_HASHER.verify(encoded_hash, password))
    except (InvalidHash, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(encoded_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.check_needs_rehash(encoded_hash)
    except (InvalidHash, VerificationError):
        return True


def hash_session_token(token: str) -> str:
    """Hash an opaque bearer token before it is persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
