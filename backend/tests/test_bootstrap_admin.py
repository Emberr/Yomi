import sqlite3

from yomi.bootstrap_admin import bootstrap_admin, main
from yomi.db.sqlite import initialize_user_db
from yomi.security.passwords import verify_password


def test_bootstrap_creates_first_active_admin(tmp_path):
    user_db = tmp_path / "user.db"

    user_id = bootstrap_admin(
        user_db_path=user_db,
        username="admin",
        display_name="Admin",
        password="bootstrap-secret",
    )

    with sqlite3.connect(user_db) as connection:
        row = connection.execute(
            """
            SELECT id, username, display_name, password_hash, enc_salt, is_admin, is_active
            FROM users
            WHERE username = ?
            """,
            ("admin",),
        ).fetchone()

    assert row[0] == user_id
    assert row[1] == "admin"
    assert row[2] == "Admin"
    assert row[3].startswith("$argon2id$")
    assert verify_password("bootstrap-secret", row[3])
    assert len(row[4]) == 16
    assert row[5] == 1
    assert row[6] == 1


def test_bootstrap_refuses_duplicate_active_admin(tmp_path):
    user_db = tmp_path / "user.db"
    bootstrap_admin(
        user_db_path=user_db,
        username="admin",
        display_name="Admin",
        password="bootstrap-secret",
    )

    exit_code = main(
        [
            "--user-db-path",
            str(user_db),
            "--username",
            "second_admin",
            "--display-name",
            "Second Admin",
        ]
    )

    with sqlite3.connect(user_db) as connection:
        admin_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND is_active = 1"
        ).fetchone()[0]
        second_admin = connection.execute(
            "SELECT 1 FROM users WHERE username = ?",
            ("second_admin",),
        ).fetchone()

    assert exit_code == 1
    assert admin_count == 1
    assert second_admin is None


def test_bootstrap_cli_uses_env_password_without_printing_or_persisting_plaintext(
    tmp_path,
    monkeypatch,
    capsys,
):
    user_db = tmp_path / "user.db"
    plaintext = "env-bootstrap-secret"
    monkeypatch.setenv("YOMI_BOOTSTRAP_ADMIN_PASSWORD", plaintext)

    exit_code = main(
        [
            "--user-db-path",
            str(user_db),
            "--username",
            "env_admin",
            "--display-name",
            "Env Admin",
        ]
    )
    captured = capsys.readouterr()

    with sqlite3.connect(user_db) as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            ("env_admin",),
        ).fetchone()

    assert exit_code == 0
    assert plaintext not in captured.out
    assert plaintext not in captured.err
    assert row[0] != plaintext
    assert row[0].startswith("$argon2id$")
    assert verify_password(plaintext, row[0])


def test_bootstrap_does_not_store_plaintext_password_anywhere(tmp_path):
    user_db = tmp_path / "user.db"
    plaintext = "not-in-database"
    initialize_user_db(user_db)

    bootstrap_admin(
        user_db_path=user_db,
        username="admin",
        display_name="Admin",
        password=plaintext,
    )

    with sqlite3.connect(user_db) as connection:
        values = [
            value
            for row in connection.execute(
                "SELECT username, display_name, email, password_hash, enc_salt FROM users"
            )
            for value in row
            if value is not None
        ]

    assert plaintext not in values
