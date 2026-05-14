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


def seed_user(settings: Settings, *, username: str = "alice", password: str = "correct-password"):
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        create_user(
            connection,
            username=username,
            display_name=username.title(),
            password=password,
        )
        connection.commit()


def make_invite(settings: Settings) -> str:
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(connection, expires_in=timedelta(days=1))
        connection.commit()
        return invite.code


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf-token")
    token = response.json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}


def test_csrf_token_endpoint_returns_token_and_readable_cookie(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/auth/csrf-token")

    token = response.json()["data"]["csrf_token"]
    cookie_header = response.headers["set-cookie"]

    assert response.status_code == 200
    assert len(token) >= 43
    assert f"yomi_csrf={token}" in cookie_header
    assert "HttpOnly" not in cookie_header
    assert "SameSite=strict" in cookie_header
    assert "Path=/" in cookie_header


def test_mutating_route_without_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )

    assert response.status_code == 403


def test_mutating_route_with_mismatched_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        client.get("/api/auth/csrf-token")
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers={"X-CSRF-Token": "wrong-token"},
        )

    assert response.status_code == 403


def test_mutating_route_with_valid_csrf_succeeds(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
    assert "yomi_session" in response.cookies


def test_get_me_does_not_require_csrf_header(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
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


def test_register_requires_valid_csrf(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "invite_code": invite_code,
                "username": "newuser",
                "display_name": "New User",
                "password": "register-password",
            },
            headers=csrf_headers(client),
        )

    assert response.status_code == 200
