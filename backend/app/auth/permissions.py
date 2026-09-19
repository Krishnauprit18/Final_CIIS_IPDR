from __future__ import annotations

from fastapi import HTTPException, status

from app.auth.repository import get_case_membership_role

CASE_VIEW_ROLES = {"OWNER", "EDITOR", "VIEWER"}
CASE_EDIT_ROLES = {"OWNER", "EDITOR"}
CASE_OWNER_ROLES = {"OWNER"}


def is_admin(user: dict) -> bool:
    return "ADMIN" in set(user.get("roles") or [])


def require_case_access(user: dict, case_id: int) -> str:
    if is_admin(user):
        return "ADMIN"

    role = get_case_membership_role(case_id=case_id, user_id=int(user["id"]))
    if role not in CASE_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case access denied",
        )
    return role


def require_case_role(user: dict, case_id: int, allowed_roles: set[str]) -> str:
    if is_admin(user):
        return "ADMIN"

    role = get_case_membership_role(case_id=case_id, user_id=int(user["id"]))
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient case permission",
        )
    return role
