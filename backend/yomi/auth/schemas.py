"""Request and response schemas for auth routes."""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    invite_code: str
    username: str
    display_name: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    is_admin: bool


class SessionResponse(BaseModel):
    id: str
    created_at: str
    expires_at: str
    last_seen_at: str
    ip_address: str | None
    user_agent: str | None
    current: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthEnvelope(BaseModel):
    data: dict[str, object]
    error: None = None
