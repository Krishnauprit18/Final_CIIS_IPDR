from __future__ import annotations

import re
from typing import Any

from app.auth import repository
from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.core.security import (
    hash_password,
    needs_rehash,
    verify_argon2,
    verify_legacy_pbkdf2,
    verify_legacy_sha256,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _password_matches(user: dict[str, Any], password: str) -> tuple[bool, bool]:
    stored_hash = user.get("password_hash") or ""
    salt = user.get("password_salt")

    if stored_hash.startswith("$argon2"):
        valid = verify_argon2(password, stored_hash)
        return valid, bool(valid and needs_rehash(stored_hash))

    if salt:
        valid = verify_legacy_pbkdf2(password, str(salt), stored_hash)
        return valid, valid

    valid = verify_legacy_sha256(password, stored_hash)
    return valid, valid


def _issue_session(user: dict[str, Any]) -> dict[str, Any]:
    roles = repository.get_roles(int(user["id"]))
    access_token, expires_in = create_access_token(
        user_id=int(user["id"]),
        username=str(user["username"]),
        roles=roles,
    )
    refresh_token, refresh_hash, refresh_expires = create_refresh_token()
    repository.create_refresh_session(
        user_id=int(user["id"]),
        token_hash=refresh_hash,
        expires_at=refresh_expires,
    )
    return {
        "success": True,
        "username": user["username"],
        "token": access_token,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "roles": roles,
        "refresh_token": refresh_token,
    }


def authenticate(identifier: str, password: str) -> dict[str, Any] | None:
    user = repository.get_user_by_identifier(identifier)
    if user is None:
        return None

    valid, should_upgrade = _password_matches(user, password)
    if not valid:
        return None

    if should_upgrade:
        repository.update_password(int(user["id"]), hash_password(password))
        user["password_hash"] = repository.get_user_by_id(int(user["id"]))["password_hash"]
        user["password_salt"] = None

    return user


def login(identifier: str, password: str) -> dict[str, Any] | None:
    user = authenticate(identifier, password)
    if user is None:
        repository.log_audit_event(
            actor_user_id=None,
            action="login",
            outcome="failure",
            metadata={"identifier": identifier[:120]},
        )
        return None

    session = _issue_session(user)
    repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="login",
        outcome="success",
        resource_type="user",
        resource_id=str(user["id"]),
    )
    return session


def register(payload: dict[str, str]) -> dict[str, Any]:
    email = (payload.get("email") or "").strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        raise ValueError("Invalid email format")

    if len(payload.get("password") or "") < 12:
        raise ValueError("Password must be at least 12 characters")

    if repository.get_user_by_identifier(email) is not None:
        raise ValueError("User with this email already exists")

    user = repository.create_user(
        username=email,
        email=email,
        password_hash=hash_password(payload["password"]),
        name=(payload.get("name") or "").strip(),
        post=(payload.get("post") or "").strip() or None,
        district=(payload.get("district") or "").strip() or None,
        thana=(payload.get("thana") or "").strip() or None,
    )
    repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="register",
        outcome="success",
        resource_type="user",
        resource_id=str(user["id"]),
    )
    return _issue_session(user)


def refresh(raw_refresh_token: str) -> dict[str, Any] | None:
    old_hash = hash_refresh_token(raw_refresh_token)
    old_session = repository.consume_refresh_session(old_hash)
    if old_session is None:
        return None

    user = repository.get_user_by_id(int(old_session["user_id"]))
    if user is None:
        return None

    session = _issue_session(user)
    repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="refresh",
        outcome="success",
        resource_type="refresh_session",
        resource_id=str(old_session["id"]),
    )
    return session


def logout(raw_refresh_token: str | None) -> None:
    if raw_refresh_token:
        repository.revoke_refresh_session(hash_refresh_token(raw_refresh_token))


def logout_all(user_id: int) -> None:
    repository.revoke_all_refresh_sessions(user_id)
    repository.log_audit_event(
        actor_user_id=user_id,
        action="logout_all",
        outcome="success",
        resource_type="user",
        resource_id=str(user_id),
    )


def change_password(user: dict[str, Any], current_password: str, new_password: str) -> None:
    if len(new_password) < 12:
        raise ValueError("Password must be at least 12 characters")

    valid, _ = _password_matches(user, current_password)
    if not valid:
        raise ValueError("Current password is incorrect")
    repository.update_password(int(user["id"]), hash_password(new_password))
    repository.revoke_all_refresh_sessions(int(user["id"]))
    repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="change_password",
        outcome="success",
        resource_type="user",
        resource_id=str(user["id"]),
    )
