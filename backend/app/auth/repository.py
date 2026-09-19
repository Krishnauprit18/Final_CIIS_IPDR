from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select, update

from app.db.models import (
    AuditEvent,
    Case,
    CaseMembership,
    RefreshSession,
    Role,
    User,
    UserRole,
)
from app.db.session import session_scope


def user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "password_hash": user.password_hash,
        "password_salt": user.password_salt,
        "name": user.name,
        "post": user.post,
        "district": user.district,
        "thana": user.thana,
        "created_at": user.created_at,
    }


def get_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    value = identifier.strip()
    with session_scope() as db:
        user = db.scalar(
            select(User).where(
                or_(
                    User.username == value,
                    User.email == value.lower(),
                )
            )
        )
        return user_to_dict(user) if user else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with session_scope() as db:
        user = db.get(User, user_id)
        return user_to_dict(user) if user else None


def create_user(
    *,
    username: str,
    email: str,
    password_hash: str,
    name: str,
    post: str | None,
    district: str | None,
    thana: str | None,
) -> dict[str, Any]:
    now = datetime.utcnow()
    with session_scope() as db:
        user = User(
            username=username,
            email=email.lower(),
            password_hash=password_hash,
            password_salt=None,
            name=name,
            post=post,
            district=district,
            thana=thana,
            created_at=now,
        )
        db.add(user)
        db.flush()

        investigator = db.scalar(select(Role).where(Role.name == "INVESTIGATOR"))
        if investigator is None:
            raise RuntimeError("INVESTIGATOR role is missing")
        db.add(UserRole(user_id=user.id, role_id=investigator.id))
        db.flush()
        return user_to_dict(user)


def update_password(user_id: int, password_hash: str) -> None:
    with session_scope() as db:
        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(password_hash=password_hash, password_salt=None)
        )


def update_profile(user_id: int, updates: dict[str, Any]) -> None:
    allowed = {"name", "post", "district", "thana"}
    values = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not values:
        return
    with session_scope() as db:
        db.execute(update(User).where(User.id == user_id).values(**values))


def get_roles(user_id: int) -> list[str]:
    with session_scope() as db:
        rows = db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.name)
        ).scalars().all()
        return list(rows)


def create_refresh_session(*, user_id: int, token_hash: str, expires_at: datetime) -> str:
    session_id = uuid.uuid4().hex
    now = datetime.utcnow()
    with session_scope() as db:
        db.add(
            RefreshSession(
                id=session_id,
                user_id=user_id,
                token_hash=token_hash,
                created_at=now,
                expires_at=expires_at,
                revoked_at=None,
                last_used_at=None,
            )
        )
    return session_id


def consume_refresh_session(token_hash: str) -> dict[str, Any] | None:
    now = datetime.utcnow()
    with session_scope() as db:
        row = db.scalar(
            select(RefreshSession)
            .where(RefreshSession.token_hash == token_hash)
            .with_for_update()
        )
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            return None
        row.revoked_at = now
        row.last_used_at = now
        return {"id": row.id, "user_id": row.user_id}


def revoke_refresh_session(token_hash: str) -> bool:
    now = datetime.utcnow()
    with session_scope() as db:
        result = db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.token_hash == token_hash,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, last_used_at=now)
        )
        return bool(result.rowcount)


def revoke_all_refresh_sessions(user_id: int) -> None:
    now = datetime.utcnow()
    with session_scope() as db:
        db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )


def add_case_membership(*, case_id: int, user_id: int, role: str) -> None:
    with session_scope() as db:
        existing = db.scalar(
            select(CaseMembership).where(
                CaseMembership.case_id == case_id,
                CaseMembership.user_id == user_id,
            )
        )
        if existing:
            existing.role = role
        else:
            db.add(
                CaseMembership(
                    case_id=case_id,
                    user_id=user_id,
                    role=role,
                    created_at=datetime.utcnow(),
                )
            )


def get_case_membership_role(*, case_id: int, user_id: int) -> str | None:
    with session_scope() as db:
        return db.scalar(
            select(CaseMembership.role).where(
                CaseMembership.case_id == case_id,
                CaseMembership.user_id == user_id,
            )
        )


def list_accessible_cases(user_id: int, *, is_admin: bool) -> list[dict[str, Any]]:
    with session_scope() as db:
        query = select(Case).order_by(Case.id.desc())
        if not is_admin:
            query = (
                query.join(CaseMembership, CaseMembership.case_id == Case.id)
                .where(CaseMembership.user_id == user_id)
            )
        rows = db.scalars(query).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "created_by": row.created_by,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def log_audit_event(
    *,
    actor_user_id: int | None,
    action: str,
    outcome: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    source_ip: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = json.dumps(metadata or {}, separators=(",", ":"), default=str)
    with session_scope() as db:
        db.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                request_id=request_id,
                source_ip=source_ip,
                metadata_json=safe_metadata,
                created_at=datetime.utcnow(),
            )
        )


def list_case_memberships(case_id: int) -> list[dict[str, Any]]:
    with session_scope() as db:
        rows = db.execute(
            select(CaseMembership, User)
            .join(User, User.id == CaseMembership.user_id)
            .where(CaseMembership.case_id == case_id)
            .order_by(User.username)
        ).all()
        return [
            {
                "user_id": membership.user_id,
                "username": user.username,
                "role": membership.role,
                "created_at": membership.created_at,
            }
            for membership, user in rows
        ]
