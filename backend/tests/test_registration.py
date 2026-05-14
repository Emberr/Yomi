import sqlite3
from datetime import timedelta

from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.invites.repository import create_invite
from yomi.main import create_app
from yomi.users.repository import create_user


def make_settings(tmp_path) -> Settings:
    return Settings(
        content_db_path=tmp_path / "content.db",
        user_db_path=tmp_path / "user.db",
        behind_https=False,
        base_url="http://testserver",
        log_level="INFO",
    )


def make_invite(
    settings: Settings,
    *,
    expires_in: timedelta | None = None,
    is_admin_invite: bool = False,
) -> str:
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(
            connection,
            expires_in=expires_in,
            is_admin_invite=is_admin_invite,
        )
        connection.commit()
        return invite.code


def register_payload(invite_code: str | None = None) -> dict[str, str]:
    payload = {
        "username": "newuser",
        "display_name": "New User",
        "password": "register-password",
    }
    if invite_code is not None:
        payload["invite_code"] = invite_code
    return payload


def test_register_without_invite_fails(tmp_path):
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/auth/register", json=register_payload())

    with sqlite3.connect(settings.user_db_path) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert response.status_code == 422
    assert user_count == 0


def test_register_with_invalid_invite_fails(tmp_path):
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json=register_payload("not-a-real-invite"),
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert response.status_code == 400
    assert user_count == 0


def test_register_with_expired_invite_fails(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings, expires_in=timedelta(seconds=-1))
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json=register_payload(invite_code),
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        invite_state = connection.execute(
            "SELECT used_by, used_at FROM invites WHERE code = ?",
            (invite_code,),
        ).fetchone()

    assert response.status_code == 400
    assert user_count == 0
    assert invite_state == (None, None)


def test_register_with_used_invite_fails(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        first = client.post("/api/auth/register", json=register_payload(invite_code))
        second = client.post(
            "/api/auth/register",
            json={
                "invite_code": invite_code,
                "username": "seconduser",
                "display_name": "Second User",
                "password": "second-password",
            },
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert first.status_code == 200
    assert second.status_code == 400
    assert user_count == 1


def test_valid_normal_invite_creates_non_admin_user_and_marks_invite_used(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings, is_admin_invite=False)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/auth/register", json=register_payload(invite_code))

    with sqlite3.connect(settings.user_db_path) as connection:
        user = connection.execute(
            "SELECT id, is_admin FROM users WHERE username = ?",
            ("newuser",),
        ).fetchone()
        invite = connection.execute(
            "SELECT used_by, used_at FROM invites WHERE code = ?",
            (invite_code,),
        ).fetchone()

    assert response.status_code == 200
    assert response.json()["data"]["user"]["is_admin"] is False
    assert user[1] == 0
    assert invite[0] == user[0]
    assert invite[1] is not None


def test_valid_admin_invite_creates_admin_user(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings, is_admin_invite=True)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/auth/register", json=register_payload(invite_code))

    with sqlite3.connect(settings.user_db_path) as connection:
        is_admin = connection.execute(
            "SELECT is_admin FROM users WHERE username = ?",
            ("newuser",),
        ).fetchone()[0]

    assert response.status_code == 200
    assert response.json()["data"]["user"]["is_admin"] is True
    assert is_admin == 1


def test_successful_registration_auto_logs_in_with_server_side_session(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/auth/register", json=register_payload(invite_code))
        me = client.get("/api/auth/me")

    cookie_header = response.headers["set-cookie"]
    with sqlite3.connect(settings.user_db_path) as connection:
        session_count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    assert response.status_code == 200
    assert "yomi_session=" in cookie_header
    assert session_count == 1
    assert me.status_code == 200
    assert me.json()["data"]["user"]["username"] == "newuser"


def test_failed_registration_does_not_create_partial_user_or_use_invite(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings)
    with open_user_db(settings.user_db_path) as connection:
        create_user(
            connection,
            username="newuser",
            display_name="Existing User",
            password="existing-password",
        )
        connection.commit()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/api/auth/register", json=register_payload(invite_code))

    with sqlite3.connect(settings.user_db_path) as connection:
        user_count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?",
            ("newuser",),
        ).fetchone()[0]
        invite_state = connection.execute(
            "SELECT used_by, used_at FROM invites WHERE code = ?",
            (invite_code,),
        ).fetchone()

    assert response.status_code == 400
    assert user_count == 1
    assert invite_state == (None, None)
