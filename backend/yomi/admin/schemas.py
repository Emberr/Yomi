"""Pydantic schemas for admin API routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str | None
    is_admin: bool
    is_active: bool
    created_at: str | None
    last_login_at: str | None
    locked_until: str | None


class AdminInviteResponse(BaseModel):
    code: str
    created_by: int | None
    created_at: str | None
    expires_at: str | None
    is_admin_invite: bool
    used_by: int | None
    used_at: str | None


class CreateInviteRequest(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    is_admin: bool = False


class AuditEventResponse(BaseModel):
    id: int
    user_id: int | None
    event_type: str
    ip_address: str | None
    user_agent: str | None
    details: dict[str, object]


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    admin_users: int
    total_invites: int
    used_invites: int
