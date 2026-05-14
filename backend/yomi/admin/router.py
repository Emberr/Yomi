"""Admin-only API routes for user, invite, and audit management."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from yomi.admin.schemas import (
    AdminInviteResponse,
    AdminStatsResponse,
    AdminUserResponse,
    AuditEventResponse,
    CreateInviteRequest,
)
from yomi.audit.repository import list_audit_events_filtered, record_audit_event
from yomi.auth.csrf import require_csrf
from yomi.auth.dependencies import get_current_admin
from yomi.db.sqlite import open_user_db
from yomi.invites.repository import (
    create_invite,
    delete_invite,
    list_all_invites,
)
from yomi.users.repository import (
    UserRecord,
    count_active_admins,
    list_all_users,
    set_user_active,
    set_user_admin,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _client_host(request: Request) -> str | None:
    return None if request.client is None else request.client.host


def _get_target_user(connection, user_id: int) -> UserRecord:
    from yomi.users.repository import get_user_by_id

    user = get_user_by_id(connection, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# User listing
# ---------------------------------------------------------------------------


@router.get("/users")
def admin_list_users(
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        users = list_all_users(connection)
    return {
        "data": {
            "users": [
                AdminUserResponse(
                    id=u.id,
                    username=u.username,
                    display_name=u.display_name,
                    email=u.email,
                    is_admin=u.is_admin,
                    is_active=u.is_active,
                    created_at=u.created_at,
                    last_login_at=u.last_login_at,
                    locked_until=u.locked_until,
                ).model_dump()
                for u in users
            ]
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# User mutations
# ---------------------------------------------------------------------------


@router.post("/users/{user_id}/suspend")
def admin_suspend_user(
    user_id: int,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        target = _get_target_user(connection, user_id)

        if target.id == admin.id:
            active_admins = count_active_admins(connection)
            if active_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot suspend the only active admin",
                )

        if not set_user_active(connection, user_id=user_id, is_active=False):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        record_audit_event(
            connection,
            event_type="admin_user_suspend",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={"target_user_id": user_id, "target_username": target.username},
        )
        connection.commit()

    return {"data": {"ok": True}, "error": None}


@router.post("/users/{user_id}/unsuspend")
def admin_unsuspend_user(
    user_id: int,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        target = _get_target_user(connection, user_id)

        if not set_user_active(connection, user_id=user_id, is_active=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        record_audit_event(
            connection,
            event_type="admin_user_unsuspend",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={"target_user_id": user_id, "target_username": target.username},
        )
        connection.commit()

    return {"data": {"ok": True}, "error": None}


@router.post("/users/{user_id}/promote")
def admin_promote_user(
    user_id: int,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        target = _get_target_user(connection, user_id)

        if not set_user_admin(connection, user_id=user_id, is_admin=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        record_audit_event(
            connection,
            event_type="admin_user_promote",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={"target_user_id": user_id, "target_username": target.username},
        )
        connection.commit()

    return {"data": {"ok": True}, "error": None}


@router.post("/users/{user_id}/demote")
def admin_demote_user(
    user_id: int,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        target = _get_target_user(connection, user_id)

        if target.is_admin:
            active_admins = count_active_admins(connection)
            if active_admins <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the only active admin",
                )

        if not set_user_admin(connection, user_id=user_id, is_admin=False):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        record_audit_event(
            connection,
            event_type="admin_user_demote",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={"target_user_id": user_id, "target_username": target.username},
        )
        connection.commit()

    return {"data": {"ok": True}, "error": None}


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    # Deferred to Phase 6: cascade behavior, audit tombstone, and
    # encrypted-key cleanup are not yet tested.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "User deletion is not yet implemented. "
            "It will be available in Phase 6 with full cascade and key-loss handling."
        ),
    )


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    # Deferred to Phase 6: admin password reset destroys the target user's
    # encryption key, making all their stored API keys unrecoverable.
    # The full key-loss flow (flag on user, re-entry prompt on next login)
    # must be implemented and tested before this endpoint is live.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Admin password reset is not yet implemented. "
            "Warning: resetting a user's password will permanently destroy their "
            "encrypted API keys, which cannot be recovered without the original password."
        ),
    )


# ---------------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------------


@router.get("/invites")
def admin_list_invites(
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        invites = list_all_invites(connection)
    return {
        "data": {
            "invites": [
                AdminInviteResponse(
                    code=inv.code,
                    created_by=inv.created_by,
                    created_at=None if inv.created_at is None else inv.created_at.isoformat(),
                    expires_at=None if inv.expires_at is None else inv.expires_at.isoformat(),
                    is_admin_invite=inv.is_admin_invite,
                    used_by=inv.used_by,
                    used_at=None if inv.used_at is None else inv.used_at.isoformat(),
                ).model_dump()
                for inv in invites
            ]
        },
        "error": None,
    }


@router.post("/invites")
def admin_create_invite(
    payload: CreateInviteRequest,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    expires_in = (
        timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(
            connection,
            created_by=admin.id,
            expires_in=expires_in,
            is_admin_invite=payload.is_admin,
        )
        record_audit_event(
            connection,
            event_type="admin_invite_create",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={
                "is_admin_invite": invite.is_admin_invite,
                "expires_in_days": payload.expires_in_days,
            },
        )
        connection.commit()

    return {
        "data": {
            "invite": AdminInviteResponse(
                code=invite.code,
                created_by=invite.created_by,
                created_at=None,
                expires_at=None if invite.expires_at is None else invite.expires_at.isoformat(),
                is_admin_invite=invite.is_admin_invite,
                used_by=invite.used_by,
                used_at=None if invite.used_at is None else invite.used_at.isoformat(),
            ).model_dump()
        },
        "error": None,
    }


@router.delete("/invites/{code}")
def admin_delete_invite(
    code: str,
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        deleted = delete_invite(connection, code)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found or already used",
            )
        record_audit_event(
            connection,
            event_type="admin_invite_delete",
            user_id=admin.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={},
        )
        connection.commit()

    return {"data": {"ok": True}, "error": None}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@router.get("/audit-log")
def admin_audit_log(
    request: Request,
    event_type: str | None = None,
    user_id: int | None = None,
    limit: int = 200,
    admin: UserRecord = Depends(get_current_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        events = list_audit_events_filtered(
            connection,
            event_type=event_type,
            user_id=user_id,
            limit=limit,
        )
    return {
        "data": {
            "events": [
                AuditEventResponse(
                    id=e.id,
                    user_id=e.user_id,
                    event_type=e.event_type,
                    ip_address=e.ip_address,
                    user_agent=e.user_agent,
                    details=e.details,
                ).model_dump()
                for e in events
            ]
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats")
def admin_stats(
    request: Request,
    admin: UserRecord = Depends(get_current_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        total_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_active = 1"
        ).fetchone()[0]
        admin_users = connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1"
        ).fetchone()[0]
        total_invites = connection.execute("SELECT COUNT(*) FROM invites").fetchone()[0]
        used_invites = connection.execute(
            "SELECT COUNT(*) FROM invites WHERE used_by IS NOT NULL"
        ).fetchone()[0]

    return {
        "data": AdminStatsResponse(
            total_users=total_users,
            active_users=active_users,
            admin_users=admin_users,
            total_invites=total_invites,
            used_invites=used_invites,
        ).model_dump(),
        "error": None,
    }
