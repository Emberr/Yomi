"""SQLite connection and Phase 1 schema helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

PHASE_1_USER_SCHEMA_VERSION = "1"
CONTENT_METADATA_TABLE = "content_metadata"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        uri = f"file:{path}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    _ensure_parent(path)
    return sqlite3.connect(path)


def apply_common_pragmas(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA cache_size=-32000")
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    cache_size = connection.execute("PRAGMA cache_size").fetchone()[0]
    return {
        "foreign_keys": foreign_keys,
        "cache_size": cache_size,
    }


def apply_writable_pragmas(connection: sqlite3.Connection) -> dict[str, Any]:
    common = apply_common_pragmas(connection)
    journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    connection.execute("PRAGMA synchronous=NORMAL")
    synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
    return {
        **common,
        "journal_mode": journal_mode,
        "synchronous": synchronous,
    }


def open_user_db(path: Path) -> sqlite3.Connection:
    connection = _connect(path, read_only=False)
    apply_writable_pragmas(connection)
    return connection


def open_content_db_readonly(path: Path) -> sqlite3.Connection:
    connection = _connect(path, read_only=True)
    apply_common_pragmas(connection)
    return connection


def initialize_user_db(path: Path) -> None:
    with open_user_db(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO user_metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (PHASE_1_USER_SCHEMA_VERSION,),
        )
        connection.commit()


def _user_metadata_value(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM user_metadata WHERE key = ?",
        (key,),
    ).fetchone()
    return None if row is None else str(row[0])


def _content_metadata_value(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM content_metadata WHERE key = ?",
        (key,),
    ).fetchone()
    return None if row is None else str(row[0])


def user_db_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path), "schema_version": None}

    try:
        with open_user_db(path) as connection:
            version = _user_metadata_value(connection, "schema_version")
    except sqlite3.Error as exc:
        return {
            "status": "error",
            "path": str(path),
            "schema_version": None,
            "error": str(exc),
        }

    return {
        "status": "ok" if version else "degraded",
        "path": str(path),
        "schema_version": version,
    }


def content_db_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path), "schema_version": None}

    try:
        with open_content_db_readonly(path) as connection:
            version = _content_metadata_value(connection, "schema_version")
    except sqlite3.Error as exc:
        return {
            "status": "degraded",
            "path": str(path),
            "schema_version": None,
            "error": str(exc),
        }

    return {
        "status": "ok" if version else "degraded",
        "path": str(path),
        "schema_version": version,
    }
