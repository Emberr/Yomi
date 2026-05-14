import sqlite3

from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.main import create_app
from yomi.users.repository import create_user


def make_settings(tmp_path, *, behind_https: bool = False) -> Settings:
    return Settings(
        content_db_path=tmp_path / "content.db",
        user_db_path=tmp_path / "user.db",
        behind_https=behind_https,
        base_url="https://testserver" if behind_https else "http://testserver",
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


def session_rows(user_db) -> list[tuple[str, int, int]]:
    with sqlite3.connect(user_db) as connection:
        return connection.execute(
            "SELECT id, user_id, revoked FROM sessions ORDER BY created_at"
        ).fetchall()


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf-token")
    token = response.json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}


def test_login_succeeds_creates_server_side_session_and_sets_cookie(tmp_path):
    settings = make_settings(tmp_path)
    user = seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["username"] == "alice"
    cookie_header = response.headers["set-cookie"]
    assert "yomi_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header
    assert "Path=/" in cookie_header
    assert "Secure" not in cookie_header

    rows = session_rows(settings.user_db_path)
    assert len(rows) == 1
    assert rows[0][1] == user.id
    assert rows[0][2] == 0
    assert len(response.cookies["yomi_session"]) >= 43


def test_login_sets_secure_cookie_when_behind_https(tmp_path):
    settings = make_settings(tmp_path, behind_https=True)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app, base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"]
    assert "Secure" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=strict" in cookie_header
    assert "Path=/" in cookie_header


def test_login_fails_with_wrong_password_and_creates_no_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "wrong-password"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 401
    assert session_rows(settings.user_db_path) == []


def test_repeated_login_creates_fresh_session_token(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        first = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )
        second = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    first_token = first.cookies["yomi_session"]
    second_token = second.cookies["yomi_session"]
    rows = session_rows(settings.user_db_path)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first_token != second_token
    assert {row[0] for row in rows} == {first_token, second_token}


def test_me_returns_current_user_with_valid_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )
        response = client.get("/api/auth/me")

    assert login.status_code == 200
    assert response.status_code == 200
    assert response.json()["data"]["user"]["username"] == "alice"


def test_logout_revokes_current_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )
        token = login.cookies["yomi_session"]
        logout = client.post("/api/auth/logout", headers=csrf_headers(client))
        me_after_logout = client.get("/api/auth/me")

    with sqlite3.connect(settings.user_db_path) as connection:
        revoked = connection.execute(
            "SELECT revoked FROM sessions WHERE id = ?",
            (token,),
        ).fetchone()[0]

    assert logout.status_code == 200
    assert revoked == 1
    assert me_after_logout.status_code == 401


def test_logout_everywhere_revokes_all_sessions_for_current_user(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as first_client, TestClient(app) as second_client:
        first_client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(first_client),
        )
        second_client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(second_client),
        )
        response = first_client.post(
            "/api/auth/logout-everywhere",
            headers=csrf_headers(first_client),
        )
        first_me = first_client.get("/api/auth/me")
        second_me = second_client.get("/api/auth/me")

    with sqlite3.connect(settings.user_db_path) as connection:
        revoked_values = {
            row[0] for row in connection.execute("SELECT revoked FROM sessions")
        }

    assert response.status_code == 200
    assert revoked_values == {1}
    assert first_me.status_code == 401
    assert second_me.status_code == 401


def test_sessions_list_only_returns_current_users_sessions(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="alice-password")
    seed_user(settings, username="bob", password="bob-password")
    app = create_app(settings)

    with TestClient(app) as alice_client, TestClient(app) as bob_client:
        alice_client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alice-password"},
            headers=csrf_headers(alice_client),
        )
        alice_client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alice-password"},
            headers=csrf_headers(alice_client),
        )
        bob_login = bob_client.post(
            "/api/auth/login",
            json={"username": "bob", "password": "bob-password"},
            headers=csrf_headers(bob_client),
        )
        response = alice_client.get("/api/auth/sessions")

    session_ids = {session["id"] for session in response.json()["data"]["sessions"]}

    assert response.status_code == 200
    assert len(session_ids) == 2
    assert bob_login.cookies["yomi_session"] not in session_ids


def test_deleting_session_cannot_delete_another_users_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="alice-password")
    seed_user(settings, username="bob", password="bob-password")
    app = create_app(settings)

    with TestClient(app) as alice_client, TestClient(app) as bob_client:
        alice_client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alice-password"},
            headers=csrf_headers(alice_client),
        )
        bob_login = bob_client.post(
            "/api/auth/login",
            json={"username": "bob", "password": "bob-password"},
            headers=csrf_headers(bob_client),
        )
        bob_token = bob_login.cookies["yomi_session"]
        response = alice_client.delete(
            f"/api/auth/sessions/{bob_token}",
            headers=csrf_headers(alice_client),
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        bob_revoked = connection.execute(
            "SELECT revoked FROM sessions WHERE id = ?",
            (bob_token,),
        ).fetchone()[0]

    assert response.status_code == 404
    assert bob_revoked == 0
