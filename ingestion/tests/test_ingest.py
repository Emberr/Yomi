import sqlite3
from pathlib import Path

from ingest import CONTENT_SCHEMA_VERSION, IngestionSettings, initialize_content_db


def _metadata_version(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT value FROM content_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]


def test_settings_load_content_db_path_only(monkeypatch):
    monkeypatch.setenv("DB_CONTENT_PATH", "/tmp/yomi-content.db")
    monkeypatch.setenv("DB_USER_PATH", "/tmp/yomi-user.db")

    settings = IngestionSettings.from_env()

    assert settings.content_db_path == Path("/tmp/yomi-content.db")


def test_initialize_content_db_creates_metadata_marker(tmp_path):
    content_db = tmp_path / "content.db"

    result = initialize_content_db(content_db)

    assert content_db.exists()
    assert result["schema_version"] == CONTENT_SCHEMA_VERSION
    assert _metadata_version(content_db) == CONTENT_SCHEMA_VERSION


def test_initialize_content_db_is_idempotent(tmp_path):
    content_db = tmp_path / "content.db"

    first = initialize_content_db(content_db)
    second = initialize_content_db(content_db)

    assert first["schema_version"] == CONTENT_SCHEMA_VERSION
    assert second["schema_version"] == CONTENT_SCHEMA_VERSION
    assert _metadata_version(content_db) == CONTENT_SCHEMA_VERSION


def test_initialize_content_db_never_touches_user_db(tmp_path, monkeypatch):
    content_db = tmp_path / "content.db"
    user_db = tmp_path / "user.db"
    monkeypatch.setenv("DB_USER_PATH", str(user_db))

    initialize_content_db(content_db)

    assert content_db.exists()
    assert not user_db.exists()
