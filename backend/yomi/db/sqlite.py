"""SQLite connection and user database schema helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

USER_SCHEMA_VERSION = "3"
CONTENT_METADATA_TABLE = "content_metadata"


USER_DB_MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "0001_user_metadata",
        """
        CREATE TABLE IF NOT EXISTS user_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT INTO user_metadata (key, value)
        VALUES ('schema_version', '1')
        ON CONFLICT(key) DO NOTHING;
        """,
    ),
    (
        "0002_auth_multiuser_core",
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            enc_salt BLOB NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login_at DATETIME,
            failed_logins INTEGER NOT NULL DEFAULT 0,
            locked_until DATETIME
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            revoked INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

        CREATE TABLE IF NOT EXISTS invites (
            code TEXT PRIMARY KEY,
            created_by INTEGER REFERENCES users(id),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            is_admin_invite INTEGER NOT NULL DEFAULT 0,
            used_by INTEGER REFERENCES users(id),
            used_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS user_secrets (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            nonce BLOB NOT NULL,
            ciphertext BLOB NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, provider)
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            details TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_event_time ON audit_log(event_type, timestamp);

        CREATE TABLE IF NOT EXISTS instance_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        UPDATE user_metadata
        SET value = '2'
        WHERE key = 'schema_version';
        """,
    ),
    (
        "0003_srs_core",
        """
        CREATE TABLE IF NOT EXISTS srs_cards (
            id              INTEGER PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            card_type       TEXT NOT NULL,
            content_id      INTEGER NOT NULL,
            content_table   TEXT NOT NULL,
            state           TEXT NOT NULL DEFAULT 'New',
            difficulty      REAL,
            stability       REAL,
            step            INTEGER,
            last_review     DATETIME,
            due             DATETIME NOT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            suspended       INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_cards_user_due
            ON srs_cards(user_id, due) WHERE suspended = 0;
        CREATE INDEX IF NOT EXISTS idx_cards_user_type
            ON srs_cards(user_id, card_type, due);

        CREATE TABLE IF NOT EXISTS review_history (
            id                INTEGER PRIMARY KEY,
            card_id           INTEGER NOT NULL REFERENCES srs_cards(id) ON DELETE CASCADE,
            user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reviewed_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            rating            INTEGER NOT NULL,
            user_answer       TEXT,
            ai_score          REAL,
            ai_feedback       TEXT,
            ai_overridden     INTEGER NOT NULL DEFAULT 0,
            time_taken_ms     INTEGER,
            state_before      TEXT,
            stability_before  REAL,
            difficulty_before REAL
        );
        CREATE INDEX IF NOT EXISTS idx_history_card_time
            ON review_history(card_id, reviewed_at);
        CREATE INDEX IF NOT EXISTS idx_history_user_time
            ON review_history(user_id, reviewed_at);

        CREATE TABLE IF NOT EXISTS lesson_completions (
            id           INTEGER PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            grammar_id   INTEGER NOT NULL,
            completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_lessons_user
            ON lesson_completions(user_id);

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id           INTEGER PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            quiz_type    TEXT NOT NULL,
            grammar_id   INTEGER,
            vocab_id     INTEGER,
            question     TEXT NOT NULL,
            user_answer  TEXT,
            correct      INTEGER,
            attempted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_quiz_user_time
            ON quiz_attempts(user_id, attempted_at);

        CREATE TABLE IF NOT EXISTS saved_sentences (
            id          INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            japanese    TEXT NOT NULL,
            romaji      TEXT,
            translation TEXT,
            notes       TEXT,
            tags        TEXT,
            source      TEXT,
            saved_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_saved_user
            ON saved_sentences(user_id);

        CREATE TABLE IF NOT EXISTS daily_activity (
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            date         DATE NOT NULL,
            reviews_done INTEGER NOT NULL DEFAULT 0,
            lessons_done INTEGER NOT NULL DEFAULT 0,
            minutes_est  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, date)
        );

        UPDATE user_metadata
        SET value = '3'
        WHERE key = 'schema_version';
        """,
    ),
)


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
        apply_user_db_migrations(connection)
        connection.commit()


def apply_user_db_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS applied_migrations (
            id TEXT PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        row[0]
        for row in connection.execute("SELECT id FROM applied_migrations").fetchall()
    }

    for migration_id, sql in USER_DB_MIGRATIONS:
        if migration_id in applied:
            continue
        connection.executescript(sql)
        connection.execute(
            "INSERT INTO applied_migrations (id) VALUES (?)",
            (migration_id,),
        )


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
