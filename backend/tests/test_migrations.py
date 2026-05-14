import sqlite3

import pytest

from yomi.db.sqlite import initialize_user_db, open_user_db


REQUIRED_TABLES = {
    "applied_migrations",
    "audit_log",
    "daily_activity",
    "instance_settings",
    "invites",
    "lesson_completions",
    "quiz_attempts",
    "review_history",
    "saved_sentences",
    "sessions",
    "srs_cards",
    "user_metadata",
    "user_secrets",
    "user_settings",
    "users",
}

REQUIRED_INDEXES = {
    "idx_audit_event_time",
    "idx_audit_user_time",
    "idx_cards_user_due",
    "idx_cards_user_type",
    "idx_history_card_time",
    "idx_history_user_time",
    "idx_lessons_user",
    "idx_quiz_user_time",
    "idx_saved_user",
    "idx_sessions_expires",
    "idx_sessions_user",
}


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def index_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
    }


def column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def foreign_key_targets(connection: sqlite3.Connection, table: str) -> set[tuple[str, str]]:
    return {
        (row[2], row[3])
        for row in connection.execute(f"PRAGMA foreign_key_list({table})")
    }


def test_all_migrations_create_expected_tables_and_indexes(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        tables = table_names(connection)
        indexes = index_names(connection)
        schema_version = connection.execute(
            "SELECT value FROM user_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]
        applied_migrations = {
            row[0] for row in connection.execute("SELECT id FROM applied_migrations")
        }

    assert tables == REQUIRED_TABLES
    assert REQUIRED_INDEXES <= indexes
    assert schema_version == "3"
    assert applied_migrations == {
        "0001_user_metadata",
        "0002_auth_multiuser_core",
        "0003_srs_core",
    }


def test_phase_2_auth_security_tables_and_indexes_are_created(tmp_path):
    """Backward-compat alias — phase 2 tables must still be present after 0003."""
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        tables = table_names(connection)
        indexes = index_names(connection)

    phase_2_tables = {
        "applied_migrations", "audit_log", "instance_settings", "invites",
        "sessions", "user_metadata", "user_secrets", "user_settings", "users",
    }
    phase_2_indexes = {
        "idx_audit_event_time", "idx_audit_user_time",
        "idx_sessions_expires", "idx_sessions_user",
    }
    assert phase_2_tables <= tables
    assert phase_2_indexes <= indexes


def test_user_secrets_schema_has_only_encrypted_secret_material(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        columns = column_names(connection, "user_secrets")

    assert {"user_id", "provider", "nonce", "ciphertext", "updated_at"} == columns
    assert "api_key" not in columns
    assert "plaintext" not in columns
    assert "secret" not in columns


def test_auth_tables_have_required_foreign_keys(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        session_fks = foreign_key_targets(connection, "sessions")
        invite_fks = foreign_key_targets(connection, "invites")
        secret_fks = foreign_key_targets(connection, "user_secrets")
        setting_fks = foreign_key_targets(connection, "user_settings")

    assert ("users", "user_id") in session_fks
    assert ("users", "created_by") in invite_fks
    assert ("users", "used_by") in invite_fks
    assert ("users", "user_id") in secret_fks
    assert ("users", "user_id") in setting_fks


def test_user_db_foreign_keys_are_enabled_and_enforced(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)

    with open_user_db(user_db) as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO sessions (id, user_id, expires_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                ("missing-user-session", 999),
            )

    assert foreign_keys == 1


def test_initialize_user_db_is_idempotent_and_preserves_existing_data(tmp_path):
    user_db = tmp_path / "user.db"

    initialize_user_db(user_db)
    with sqlite3.connect(user_db) as connection:
        connection.execute(
            """
            INSERT INTO users (username, display_name, password_hash, enc_salt)
            VALUES (?, ?, ?, ?)
            """,
            ("phase2_user", "Phase 2 User", "argon2-placeholder", b"0" * 16),
        )
        connection.execute(
            """
            INSERT INTO instance_settings (key, value)
            VALUES (?, ?)
            """,
            ("registration", '{"enabled": false}'),
        )
        connection.commit()

    initialize_user_db(user_db)
    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        setting_value = connection.execute(
            "SELECT value FROM instance_settings WHERE key = ?",
            ("registration",),
        ).fetchone()[0]
        migration_count = connection.execute(
            "SELECT COUNT(*) FROM applied_migrations"
        ).fetchone()[0]
        tables = table_names(connection)

    assert user_count == 1
    assert setting_value == '{"enabled": false}'
    assert migration_count == 3
    assert tables == REQUIRED_TABLES


def test_migration_0003_srs_tables_have_correct_schema(tmp_path):
    user_db = tmp_path / "user.db"
    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        srs_cols = column_names(connection, "srs_cards")
        history_cols = column_names(connection, "review_history")
        activity_cols = column_names(connection, "daily_activity")

    assert {"id", "user_id", "card_type", "content_id", "content_table",
            "state", "difficulty", "stability", "step", "last_review",
            "due", "created_at", "suspended"} == srs_cols
    assert {"id", "card_id", "user_id", "reviewed_at", "rating",
            "user_answer", "ai_score", "ai_feedback", "ai_overridden",
            "time_taken_ms", "state_before", "stability_before",
            "difficulty_before"} == history_cols
    assert {"user_id", "date", "reviews_done", "lessons_done", "minutes_est"} == activity_cols


def test_migration_0003_foreign_keys_cascade(tmp_path):
    user_db = tmp_path / "user.db"
    initialize_user_db(user_db)

    with open_user_db(user_db) as connection:
        srs_card_fks = foreign_key_targets(connection, "srs_cards")
        history_fks = foreign_key_targets(connection, "review_history")
        activity_fks = foreign_key_targets(connection, "daily_activity")

    assert ("users", "user_id") in srs_card_fks
    assert ("users", "user_id") in history_fks
    assert ("srs_cards", "card_id") in history_fks
    assert ("users", "user_id") in activity_fks


def test_migration_0003_existing_users_survive(tmp_path):
    """Users inserted before 0003 must still be queryable after migration."""
    user_db = tmp_path / "user.db"

    # Apply only 0001 and 0002 by temporarily patching migrations
    from yomi.db import sqlite as sqlite_mod
    orig_migrations = sqlite_mod.USER_DB_MIGRATIONS
    sqlite_mod.USER_DB_MIGRATIONS = orig_migrations[:2]
    try:
        initialize_user_db(user_db)
        with sqlite3.connect(user_db) as connection:
            connection.execute(
                "INSERT INTO users (username, display_name, password_hash, enc_salt) "
                "VALUES (?, ?, ?, ?)",
                ("legacy_user", "Legacy", "argon2-placeholder", b"0" * 16),
            )
            connection.commit()
    finally:
        sqlite_mod.USER_DB_MIGRATIONS = orig_migrations

    # Now apply all migrations including 0003
    initialize_user_db(user_db)

    with sqlite3.connect(user_db) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE username='legacy_user'"
        ).fetchone()[0]
        version = connection.execute(
            "SELECT value FROM user_metadata WHERE key='schema_version'"
        ).fetchone()[0]

    assert count == 1
    assert version == "3"
