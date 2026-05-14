"""SQLite-backed user persistence helpers."""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass

from yomi.security.passwords import hash_password

ENC_SALT_BYTES = 16


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    display_name: str
    email: str | None
    password_hash: str
    enc_salt: bytes
    is_admin: bool
    is_active: bool
    failed_logins: int
    locked_until: str | None


def _user_from_row(row: sqlite3.Row | tuple[object, ...]) -> UserRecord:
    return UserRecord(
        id=int(row[0]),
        username=str(row[1]),
        display_name=str(row[2]),
        email=None if row[3] is None else str(row[3]),
        password_hash=str(row[4]),
        enc_salt=bytes(row[5]),
        is_admin=bool(row[6]),
        is_active=bool(row[7]),
        failed_logins=int(row[8]),
        locked_until=None if row[9] is None else str(row[9]),
    )


def create_user(
    connection: sqlite3.Connection,
    *,
    username: str,
    display_name: str,
    password: str,
    email: str | None = None,
    is_admin: bool = False,
    is_active: bool = True,
) -> UserRecord:
    password_hash = hash_password(password)
    enc_salt = secrets.token_bytes(ENC_SALT_BYTES)
    cursor = connection.execute(
        """
        INSERT INTO users (
            username,
            display_name,
            email,
            password_hash,
            enc_salt,
            is_admin,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            display_name,
            email,
            password_hash,
            enc_salt,
            int(is_admin),
            int(is_active),
        ),
    )
    user_id = int(cursor.lastrowid)
    user = get_user_by_id(connection, user_id)
    if user is None:
        raise RuntimeError("created user could not be loaded")
    return user


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> UserRecord | None:
    row = connection.execute(
        """
        SELECT id, username, display_name, email, password_hash, enc_salt, is_admin, is_active, failed_logins, locked_until
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    return None if row is None else _user_from_row(row)


def get_user_by_username(
    connection: sqlite3.Connection,
    username: str,
) -> UserRecord | None:
    row = connection.execute(
        """
        SELECT id, username, display_name, email, password_hash, enc_salt, is_admin, is_active, failed_logins, locked_until
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    return None if row is None else _user_from_row(row)


def active_admin_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM users
        WHERE is_admin = 1 AND is_active = 1
        LIMIT 1
        """
    ).fetchone()
    return row is not None
