import sqlite3

from yomi.db.sqlite import (
    CONTENT_METADATA_TABLE,
    content_db_status,
    initialize_user_db,
    open_content_db_readonly,
    open_user_db,
)


def test_initialize_user_db_creates_phase_2_metadata_marker(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = connection.execute(
            "SELECT value FROM user_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]

    assert "user_metadata" in tables
    assert "applied_migrations" in tables
    assert version == "3"


def test_user_db_connection_applies_required_pragmas(tmp_path):
    user_db = tmp_path / "user.db"

    with open_user_db(user_db) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        cache_size = connection.execute("PRAGMA cache_size").fetchone()[0]

    assert journal_mode == "wal"
    assert synchronous == 1
    assert foreign_keys == 1
    assert cache_size == -32000


def test_content_db_missing_is_reported_without_creation(tmp_path):
    content_db = tmp_path / "content.db"

    status = content_db_status(content_db)

    assert status["status"] == "missing"
    assert not content_db.exists()


def test_content_db_readonly_check_does_not_write(tmp_path):
    content_db = tmp_path / "content.db"
    with sqlite3.connect(content_db) as connection:
        connection.execute(
            f"CREATE TABLE {CONTENT_METADATA_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            f"INSERT INTO {CONTENT_METADATA_TABLE} (key, value) VALUES (?, ?)",
            ("schema_version", "content-v1"),
        )
        connection.commit()

    with open_content_db_readonly(content_db) as connection:
        version = connection.execute(
            f"SELECT value FROM {CONTENT_METADATA_TABLE} WHERE key = ?",
            ("schema_version",),
        ).fetchone()[0]

    assert version == "content-v1"
    assert not (tmp_path / "content.db-wal").exists()
    assert not (tmp_path / "content.db-shm").exists()
