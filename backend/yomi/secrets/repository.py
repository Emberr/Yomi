"""SQLite-backed repository for encrypted user secrets (API keys).

Only nonce + ciphertext are ever stored. Plaintext is never written to disk.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class UserSecretRecord:
    user_id: int
    provider: str
    nonce: bytes
    ciphertext: bytes


def _secret_from_row(row: sqlite3.Row | tuple[object, ...]) -> UserSecretRecord:
    return UserSecretRecord(
        user_id=int(row[0]),
        provider=str(row[1]),
        nonce=bytes(row[2]),
        ciphertext=bytes(row[3]),
    )


def upsert_user_secret(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    provider: str,
    nonce: bytes,
    ciphertext: bytes,
) -> None:
    connection.execute(
        """
        INSERT INTO user_secrets (user_id, provider, nonce, ciphertext, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, provider)
        DO UPDATE SET
            nonce = excluded.nonce,
            ciphertext = excluded.ciphertext,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, provider, nonce, ciphertext),
    )


def delete_user_secret(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    provider: str,
) -> bool:
    cursor = connection.execute(
        "DELETE FROM user_secrets WHERE user_id = ? AND provider = ?",
        (user_id, provider),
    )
    return cursor.rowcount > 0


def list_user_secrets(
    connection: sqlite3.Connection,
    user_id: int,
) -> list[UserSecretRecord]:
    rows = connection.execute(
        """
        SELECT user_id, provider, nonce, ciphertext
        FROM user_secrets
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    return [_secret_from_row(row) for row in rows]


def get_user_secret(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    provider: str,
) -> UserSecretRecord | None:
    row = connection.execute(
        """
        SELECT user_id, provider, nonce, ciphertext
        FROM user_secrets
        WHERE user_id = ? AND provider = ?
        """,
        (user_id, provider),
    ).fetchone()
    return None if row is None else _secret_from_row(row)
