from __future__ import annotations

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    return _PASSWORD_HASHER.hash(password)


def verify_argon2(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.check_needs_rehash(password_hash)
    except InvalidHash:
        return True


def verify_legacy_pbkdf2(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash_hex)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        150_000,
    )
    return hmac.compare_digest(actual, expected)


def verify_legacy_sha256(password: str, expected_hash_hex: str) -> bool:
    actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(actual, expected_hash_hex or "")
