"""Server-side session persistence."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

SESSION_COOKIE_NAME = "yomi_session"
SESSION_TOKEN_BYTES = 32
SESSION_LIFETIME = timedelta(days=7)


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    ip_address: str | None
    user_agent: str | None
    revoked: bool


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _session_from_row(row: sqlite3.Row | tuple[object, ...]) -> SessionRecord:
    return SessionRecord(
        id=str(row[0]),
        user_id=int(row[1]),
        created_at=_parse_timestamp(str(row[2])),
        expires_at=_parse_timestamp(str(row[3])),
        last_seen_at=_parse_timestamp(str(row[4])),
        ip_address=None if row[5] is None else str(row[5]),
        user_agent=None if row[6] is None else str(row[6]),
        revoked=bool(row[7]),
    )


def create_session(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    ip_address: str | None,
    user_agent: str | None,
) -> SessionRecord:
    now = _utc_now()
    expires_at = now + SESSION_LIFETIME
    token = generate_session_token()
    connection.execute(
        """
        INSERT INTO sessions (
            id,
            user_id,
            created_at,
            expires_at,
            last_seen_at,
            ip_address,
            user_agent,
            revoked
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            token,
            user_id,
            _format_timestamp(now),
            _format_timestamp(expires_at),
            _format_timestamp(now),
            ip_address,
            user_agent,
        ),
    )
    session = get_session_by_id(connection, token)
    if session is None:
        raise RuntimeError("created session could not be loaded")
    return session


def get_session_by_id(
    connection: sqlite3.Connection,
    session_id: str,
) -> SessionRecord | None:
    row = connection.execute(
        """
        SELECT id, user_id, created_at, expires_at, last_seen_at, ip_address, user_agent, revoked
        FROM sessions
        WHERE id = ?
        """,
        (session_id,),
    ).fetchone()
    return None if row is None else _session_from_row(row)


def get_valid_session(
    connection: sqlite3.Connection,
    session_id: str | None,
) -> SessionRecord | None:
    if not session_id:
        return None
    session = get_session_by_id(connection, session_id)
    if session is None or session.revoked or session.expires_at <= _utc_now():
        return None
    connection.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
        (_format_timestamp(_utc_now()), session_id),
    )
    return get_session_by_id(connection, session_id)


def revoke_session(connection: sqlite3.Connection, session_id: str) -> None:
    connection.execute(
        "UPDATE sessions SET revoked = 1 WHERE id = ?",
        (session_id,),
    )


def revoke_user_session(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    session_id: str,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE sessions
        SET revoked = 1
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    )
    return cursor.rowcount > 0


def revoke_all_user_sessions(connection: sqlite3.Connection, user_id: int) -> None:
    connection.execute(
        "UPDATE sessions SET revoked = 1 WHERE user_id = ?",
        (user_id,),
    )


def list_user_sessions(
    connection: sqlite3.Connection,
    user_id: int,
) -> list[SessionRecord]:
    rows = connection.execute(
        """
        SELECT id, user_id, created_at, expires_at, last_seen_at, ip_address, user_agent, revoked
        FROM sessions
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    now = _utc_now()
    return [
        session
        for session in (_session_from_row(row) for row in rows)
        if not session.revoked and session.expires_at > now
    ]
