import sqlite3

from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.security.passwords import hash_password, verify_password
from yomi.users.repository import create_user, get_user_by_username


def test_password_hash_uses_argon2id_and_verifies_correct_password():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", password_hash)


def test_wrong_password_fails_verification():
    password_hash = hash_password("correct horse battery staple")

    assert not verify_password("wrong password", password_hash)


def test_user_creation_stores_hash_and_random_enc_salt(tmp_path):
    user_db = tmp_path / "user.db"
    initialize_user_db(user_db)

    with open_user_db(user_db) as connection:
        user_a = create_user(
            connection,
            username="admin",
            display_name="Admin",
            password="not-persisted-password",
            is_admin=True,
        )
        user_b = create_user(
            connection,
            username="second",
            display_name="Second",
            password="another-password",
        )
        connection.commit()

    assert user_a.password_hash.startswith("$argon2id$")
    assert user_a.password_hash != "not-persisted-password"
    assert verify_password("not-persisted-password", user_a.password_hash)
    assert len(user_a.enc_salt) == 16
    assert len(user_b.enc_salt) == 16
    assert user_a.enc_salt != user_b.enc_salt
    assert user_a.is_admin
    assert user_a.is_active


def test_user_creation_does_not_persist_plaintext_password(tmp_path):
    user_db = tmp_path / "user.db"
    plaintext = "plain-password-must-not-persist"
    initialize_user_db(user_db)

    with open_user_db(user_db) as connection:
        create_user(
            connection,
            username="plaincheck",
            display_name="Plain Check",
            password=plaintext,
        )
        connection.commit()

    with sqlite3.connect(user_db) as connection:
        rows = connection.execute(
            """
            SELECT username, display_name, email, password_hash, enc_salt
            FROM users
            """
        ).fetchall()

    flattened = [
        value
        for row in rows
        for value in row
        if value is not None
    ]
    assert plaintext not in flattened


def test_user_can_be_fetched_by_username(tmp_path):
    user_db = tmp_path / "user.db"
    initialize_user_db(user_db)

    with open_user_db(user_db) as connection:
        created = create_user(
            connection,
            username="lookup",
            display_name="Lookup User",
            password="lookup-password",
        )
        loaded = get_user_by_username(connection, "lookup")

    assert loaded == created
