import json
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from yomi.auth.rate_limit import LOGIN_REGISTER_LIMIT
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
        user = create_user(
            connection,
            username=username,
            display_name=username.title(),
            password=password,
        )
        connection.commit()
        return user


def make_invite(settings: Settings) -> str:
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(connection)
        connection.commit()
        return invite.code


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf-token")
    token = response.json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}


def audit_events(settings: Settings) -> list[tuple[int | None, str, dict[str, object]]]:
    with sqlite3.connect(settings.user_db_path) as connection:
        return [
            (row[0], row[1], json.loads(row[2]))
            for row in connection.execute(
                "SELECT user_id, event_type, details FROM audit_log ORDER BY id"
            )
        ]


def test_login_ip_limiter_rejects_excessive_attempts(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        responses = [
            client.post(
                "/api/auth/login",
                json={"username": f"missing-{index}", "password": "wrong"},
                headers=csrf_headers(client),
            )
            for index in range(LOGIN_REGISTER_LIMIT + 1)
        ]

    assert [response.status_code for response in responses[:-1]] == [401] * LOGIN_REGISTER_LIMIT
    assert responses[-1].status_code == 429


def test_register_ip_limiter_rejects_excessive_attempts(tmp_path):
    settings = make_settings(tmp_path)
    invite_code = make_invite(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        responses = [
            client.post(
                "/api/auth/register",
                json={
                    "invite_code": f"{invite_code}-{index}",
                    "username": f"user{index}",
                    "display_name": "User",
                    "password": "register-password",
                },
                headers=csrf_headers(client),
            )
            for index in range(LOGIN_REGISTER_LIMIT + 1)
        ]

    assert [response.status_code for response in responses[:-1]] == [400] * LOGIN_REGISTER_LIMIT
    assert responses[-1].status_code == 429


def test_account_locks_after_10_failed_logins_and_unlocks_after_expiry(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)
    base_time = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    app.state.auth_rate_limiter.now_func = lambda: base_time

    with TestClient(app) as client:
        failures = [
            client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "wrong-password"},
                headers=csrf_headers(client),
            )
            for _ in range(10)
        ]
        locked_correct_password = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

        app.state.auth_rate_limiter.now_func = lambda: base_time + timedelta(minutes=16)
        unlocked_correct_password = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        failed_logins, locked_until = connection.execute(
            "SELECT failed_logins, locked_until FROM users WHERE username = ?",
            ("alice",),
        ).fetchone()

    assert [response.status_code for response in failures] == [401] * 10
    assert locked_correct_password.status_code == 401
    assert unlocked_correct_password.status_code == 200
    assert failed_logins == 0
    assert locked_until is None


def test_successful_login_resets_failed_login_state(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        for _ in range(3):
            client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "wrong-password"},
                headers=csrf_headers(client),
            )
        success = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    with sqlite3.connect(settings.user_db_path) as connection:
        failed_logins, locked_until = connection.execute(
            "SELECT failed_logins, locked_until FROM users WHERE username = ?",
            ("alice",),
        ).fetchone()

    assert success.status_code == 200
    assert failed_logins == 0
    assert locked_until is None


def test_lockout_failure_and_success_are_audited(tmp_path):
    settings = make_settings(tmp_path)
    user = seed_user(settings)
    app = create_app(settings)
    base_time = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    app.state.auth_rate_limiter.now_func = lambda: base_time

    with TestClient(app) as client:
        for _ in range(10):
            client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "wrong-password"},
                headers=csrf_headers(client),
            )
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )
        app.state.auth_rate_limiter.now_func = lambda: base_time + timedelta(minutes=16)
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
            headers=csrf_headers(client),
        )

    events = audit_events(settings)

    assert (
        user.id,
        "login_failure",
        {"username": "alice", "reason": "account_locked"},
    ) in events
    assert (user.id, "login_success", {"username": "alice"}) in events
