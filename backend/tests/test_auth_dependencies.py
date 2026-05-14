import sqlite3

from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
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


def seed_user(settings: Settings, *, username: str, password: str, is_active: bool = True):
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        user = create_user(
            connection,
            username=username,
            display_name=username.title(),
            password=password,
            is_active=is_active,
        )
        connection.commit()
        return user


def test_me_returns_401_with_no_session(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_401_with_invalid_session(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        client.cookies.set("yomi_session", "not-a-real-session")
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_401_with_expired_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        token = login.cookies["yomi_session"]
        with sqlite3.connect(settings.user_db_path) as connection:
            connection.execute(
                "UPDATE sessions SET expires_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00+00:00", token),
            )
            connection.commit()
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_401_with_revoked_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        token = login.cookies["yomi_session"]
        with sqlite3.connect(settings.user_db_path) as connection:
            connection.execute(
                "UPDATE sessions SET revoked = 1 WHERE id = ?",
                (token,),
            )
            connection.commit()
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_inactive_user_cannot_authenticate_or_use_protected_routes(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="inactive", password="correct-password", is_active=False)
    seed_user(settings, username="active", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        inactive_login = client.post(
            "/api/auth/login",
            json={"username": "inactive", "password": "correct-password"},
        )
        active_login = client.post(
            "/api/auth/login",
            json={"username": "active", "password": "correct-password"},
        )
        token = active_login.cookies["yomi_session"]
        with sqlite3.connect(settings.user_db_path) as connection:
            connection.execute(
                "UPDATE users SET is_active = 0 WHERE username = ?",
                ("active",),
            )
            connection.commit()
        protected_response = client.get("/api/auth/me")

    with sqlite3.connect(settings.user_db_path) as connection:
        inactive_session_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE users.username = ?
            """,
            ("inactive",),
        ).fetchone()[0]
        active_session_exists = connection.execute(
            "SELECT 1 FROM sessions WHERE id = ?",
            (token,),
        ).fetchone()

    assert inactive_login.status_code == 401
    assert inactive_session_count == 0
    assert active_login.status_code == 200
    assert active_session_exists is not None
    assert protected_response.status_code == 401
