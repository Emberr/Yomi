"""Shared authentication dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from yomi.auth.sessions import SESSION_COOKIE_NAME, SessionRecord, get_valid_session
from yomi.db.sqlite import open_user_db
from yomi.users.repository import UserRecord, get_user_by_id


@dataclass(frozen=True)
class AuthenticatedUser:
    user: UserRecord
    session: SessionRecord


def get_current_auth(request: Request) -> AuthenticatedUser:
    settings = request.app.state.settings
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    with open_user_db(settings.user_db_path) as connection:
        session = get_valid_session(connection, session_token)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        user = get_user_by_id(connection, session.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        connection.commit()
        return AuthenticatedUser(user=user, session=session)


def get_current_user(request: Request) -> UserRecord:
    return get_current_auth(request).user


def get_current_admin(auth: AuthenticatedUser = Depends(get_current_auth)) -> UserRecord:
    if not auth.user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return auth.user
