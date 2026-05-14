"""SQLite-backed invite helpers."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

INVITE_CODE_BYTES = 16


@dataclass(frozen=True)
class InviteRecord:
    code: str
    created_by: int | None
    created_at: datetime | None
    expires_at: datetime | None
    is_admin_invite: bool
    used_by: int | None
    used_at: datetime | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_optional_timestamp(value: object | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _invite_from_row(row: sqlite3.Row | tuple[object, ...]) -> InviteRecord:
    return InviteRecord(
        code=str(row[0]),
        created_by=None if row[1] is None else int(row[1]),
        created_at=_parse_optional_timestamp(row[2]),
        expires_at=_parse_optional_timestamp(row[3]),
        is_admin_invite=bool(row[4]),
        used_by=None if row[5] is None else int(row[5]),
        used_at=_parse_optional_timestamp(row[6]),
    )


def create_invite(
    connection: sqlite3.Connection,
    *,
    created_by: int | None = None,
    expires_in: timedelta | None = None,
    is_admin_invite: bool = False,
) -> InviteRecord:
    code = secrets.token_urlsafe(INVITE_CODE_BYTES)
    expires_at = None if expires_in is None else _utc_now() + expires_in
    connection.execute(
        """
        INSERT INTO invites (
            code,
            created_by,
            expires_at,
            is_admin_invite
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            code,
            created_by,
            None if expires_at is None else _format_timestamp(expires_at),
            int(is_admin_invite),
        ),
    )
    invite = get_invite(connection, code)
    if invite is None:
        raise RuntimeError("created invite could not be loaded")
    return invite


def get_invite(connection: sqlite3.Connection, code: str) -> InviteRecord | None:
    row = connection.execute(
        """
        SELECT code, created_by, created_at, expires_at, is_admin_invite, used_by, used_at
        FROM invites
        WHERE code = ?
        """,
        (code,),
    ).fetchone()
    return None if row is None else _invite_from_row(row)


def validate_invite_for_registration(
    connection: sqlite3.Connection,
    code: str,
) -> InviteRecord | None:
    invite = get_invite(connection, code)
    if invite is None or invite.used_by is not None or invite.used_at is not None:
        return None
    if invite.expires_at is not None and invite.expires_at <= _utc_now():
        return None
    return invite


def list_all_invites(connection: sqlite3.Connection) -> list[InviteRecord]:
    rows = connection.execute(
        """
        SELECT code, created_by, created_at, expires_at, is_admin_invite, used_by, used_at
        FROM invites
        ORDER BY rowid
        """
    ).fetchall()
    return [_invite_from_row(row) for row in rows]


def delete_invite(connection: sqlite3.Connection, code: str) -> bool:
    cursor = connection.execute(
        "DELETE FROM invites WHERE code = ? AND used_by IS NULL",
        (code,),
    )
    return cursor.rowcount == 1


def mark_invite_used(
    connection: sqlite3.Connection,
    *,
    code: str,
    user_id: int,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE invites
        SET used_by = ?, used_at = ?
        WHERE code = ? AND used_by IS NULL AND used_at IS NULL
        """,
        (user_id, _format_timestamp(_utc_now()), code),
    )
    return cursor.rowcount == 1
