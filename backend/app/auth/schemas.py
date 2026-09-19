from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    post: str
    district: str
    thana: str


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    post: Optional[str] = None
    district: Optional[str] = None
    thana: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
