"""Authentication API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from yomi.auth.dependencies import AuthenticatedUser, get_current_auth
from yomi.auth.schemas import LoginRequest, RegisterRequest, SessionResponse, UserResponse
from yomi.auth.sessions import (
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME,
    create_session,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
    revoke_user_session,
)
from yomi.audit.repository import record_audit_event
from yomi.db.sqlite import open_user_db
from yomi.invites.repository import mark_invite_used, validate_invite_for_registration
from yomi.security.passwords import verify_password
from yomi.users.repository import UserRecord, create_user, get_user_by_username

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: UserRecord) -> dict[str, object]:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_admin=user.is_admin,
    ).model_dump()


def _set_session_cookie(
    response: Response,
    *,
    token: str,
    secure: bool,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def _client_host(request: Request) -> str | None:
    return None if request.client is None else request.client.host


@router.post("/register")
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        invite = validate_invite_for_registration(connection, payload.invite_code)
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invite code",
            )

        try:
            user = create_user(
                connection,
                username=payload.username,
                display_name=payload.display_name,
                password=payload.password,
                is_admin=invite.is_admin_invite,
            )
            if not mark_invite_used(connection, code=invite.code, user_id=user.id):
                raise sqlite3.IntegrityError("invite already used")
            session = create_session(
                connection,
                user_id=user.id,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
            )
            record_audit_event(
                connection,
                event_type="account_created",
                user_id=user.id,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
                details={
                    "username": user.username,
                    "is_admin": user.is_admin,
                },
            )
            record_audit_event(
                connection,
                event_type="invite_redeemed",
                user_id=user.id,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
                details={
                    "is_admin_invite": invite.is_admin_invite,
                },
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration could not be completed",
            ) from None

    _set_session_cookie(response, token=session.id, secure=settings.behind_https)
    return {"data": {"user": _user_response(user)}, "error": None}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        user = get_user_by_username(connection, payload.username)
        if (
            user is None
            or not user.is_active
            or not verify_password(payload.password, user.password_hash)
        ):
            record_audit_event(
                connection,
                event_type="login_failure",
                user_id=None if user is None else user.id,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
                details={"username": payload.username},
            )
            connection.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        session = create_session(
            connection,
            user_id=user.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
        )
        connection.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user.id,),
        )
        record_audit_event(
            connection,
            event_type="login_success",
            user_id=user.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={"username": user.username},
        )
        connection.commit()

    _set_session_cookie(response, token=session.id, secure=settings.behind_https)
    return {"data": {"user": _user_response(user)}, "error": None}


@router.get("/me")
def me(auth: AuthenticatedUser = Depends(get_current_auth)) -> dict[str, object]:
    return {"data": {"user": _user_response(auth.user)}, "error": None}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    auth: AuthenticatedUser = Depends(get_current_auth),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        revoke_session(connection, auth.session.id)
        record_audit_event(
            connection,
            event_type="logout",
            user_id=auth.user.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={},
        )
        connection.commit()

    _clear_session_cookie(response, secure=settings.behind_https)
    return {"data": {"ok": True}, "error": None}


@router.post("/logout-everywhere")
def logout_everywhere(
    request: Request,
    response: Response,
    auth: AuthenticatedUser = Depends(get_current_auth),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        revoke_all_user_sessions(connection, auth.user.id)
        record_audit_event(
            connection,
            event_type="logout_everywhere",
            user_id=auth.user.id,
            ip_address=_client_host(request),
            user_agent=request.headers.get("user-agent"),
            details={},
        )
        connection.commit()

    _clear_session_cookie(response, secure=settings.behind_https)
    return {"data": {"ok": True}, "error": None}


@router.get("/sessions")
def sessions(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_auth),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        user_sessions = list_user_sessions(connection, auth.user.id)

    return {
        "data": {
            "sessions": [
                SessionResponse(
                    id=session.id,
                    created_at=session.created_at.isoformat(),
                    expires_at=session.expires_at.isoformat(),
                    last_seen_at=session.last_seen_at.isoformat(),
                    ip_address=session.ip_address,
                    user_agent=session.user_agent,
                    current=session.id == auth.session.id,
                ).model_dump()
                for session in user_sessions
            ],
        },
        "error": None,
    }


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_auth),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        revoked = revoke_user_session(
            connection,
            user_id=auth.user.id,
            session_id=session_id,
        )
        if revoked:
            record_audit_event(
                connection,
                event_type="session_revoked",
                user_id=auth.user.id,
                ip_address=_client_host(request),
                user_agent=request.headers.get("user-agent"),
                details={},
            )
        connection.commit()

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return {"data": {"ok": True}, "error": None}
