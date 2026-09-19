from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth import repository, service
from app.auth.dependencies import current_user
from app.auth.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from app.core.config import AUTH_COOKIE_SECURE, REFRESH_TOKEN_DAYS

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "ciis_refresh"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/",
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
    )


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    result = service.login(payload.username, payload.password)
    if result is None:
        return {"success": False, "message": "Invalid username or password"}

    refresh_token = result.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return result


@router.post("/register")
def register(payload: RegisterRequest, response: Response):
    try:
        result = service.register(payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refresh_token = result.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return result


@router.post("/refresh")
def refresh(request: Request, response: Response):
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session required")

    result = service.refresh(raw_refresh)
    if result is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session expired or revoked")

    refresh_token = result.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return result


@router.post("/logout")
def logout(request: Request, response: Response):
    service.logout(request.cookies.get(_REFRESH_COOKIE))
    _clear_refresh_cookie(response)
    return {"success": True, "message": "Logged out successfully"}


@router.post("/logout-all")
def logout_all(response: Response, user: dict = Depends(current_user)):
    service.logout_all(int(user["id"]))
    _clear_refresh_cookie(response)
    return {"success": True, "message": "All sessions revoked"}


@router.get("/verify")
def verify_session(user: dict = Depends(current_user)):
    return {
        "success": True,
        "username": user["username"],
        "roles": user["roles"],
        "valid": True,
    }


@router.get("/me")
def get_profile(user: dict = Depends(current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "name": user.get("name"),
        "post": user.get("post"),
        "district": user.get("district"),
        "thana": user.get("thana"),
        "roles": user["roles"],
        "created_at": user.get("created_at"),
    }


@router.put("/profile")
def update_profile(payload: ProfileUpdateRequest, user: dict = Depends(current_user)):
    repository.update_profile(int(user["id"]), payload.dict(exclude_none=True))
    repository.log_audit_event(
        actor_user_id=int(user["id"]),
        action="profile_update",
        outcome="success",
        resource_type="user",
        resource_id=str(user["id"]),
    )
    return {"success": True, "message": "Profile updated"}


@router.post("/change-password")
def change_password(payload: PasswordChangeRequest, response: Response, user: dict = Depends(current_user)):
    try:
        service.change_password(user, payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _clear_refresh_cookie(response)
    return {
        "success": True,
        "message": "Password changed; refresh sessions revoked",
    }
