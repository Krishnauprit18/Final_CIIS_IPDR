from __future__ import annotations

import hashlib

from app.auth import tokens
from app.core.security import (
    hash_password,
    verify_argon2,
    verify_legacy_pbkdf2,
)
from app.db.models import Base


def test_argon2_password_roundtrip():
    encoded = hash_password("correct-horse-battery-staple")
    assert encoded.startswith("$argon2")
    assert verify_argon2("correct-horse-battery-staple", encoded)
    assert not verify_argon2("wrong-password", encoded)


def test_legacy_pbkdf2_verification():
    password = "legacy-password"
    salt = bytes.fromhex("00112233445566778899aabbccddeeff")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 150_000)
    assert verify_legacy_pbkdf2(password, salt.hex(), digest.hex())
    assert not verify_legacy_pbkdf2("wrong-password", salt.hex(), digest.hex())


def test_access_token_is_short_lived_and_signed(monkeypatch):
    monkeypatch.setattr(tokens, "AUTH_SECRET", "x" * 64)
    monkeypatch.setattr(tokens, "ACCESS_TOKEN_MINUTES", 15)

    encoded, expires_in = tokens.create_access_token(
        user_id=42,
        username="investigator@example.test",
        roles=["INVESTIGATOR"],
        session_id="session-123",
    )
    decoded = tokens.decode_access_token(encoded)

    assert expires_in == 900
    assert decoded["sub"] == "42"
    assert decoded["username"] == "investigator@example.test"
    assert decoded["roles"] == ["INVESTIGATOR"]
    assert decoded["sid"] == "session-123"
    assert decoded["type"] == "access"


def test_refresh_token_is_stored_as_hash_only():
    raw, token_hash, expires_at = tokens.create_refresh_token()
    assert raw != token_hash
    assert token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert expires_at is not None


def test_phase15_schema_tables_present():
    required = {
        "roles",
        "user_roles",
        "case_memberships",
        "refresh_sessions",
        "audit_events",
    }
    assert required.issubset(set(Base.metadata.tables))
