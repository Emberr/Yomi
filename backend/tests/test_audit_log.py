import json

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


def make_invite(settings: Settings) -> str:
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(connection)
        connection.commit()
        return invite.code


def seed_user(settings: Settings, *, username: str, password: str):
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


def audit_rows(settings: Settings) -> list[tuple[int | None, str, str]]:
    with open_user_db(settings.user_db_path) as connection:
        return connection.execute(
            """
            SELECT user_id, event_type, details
            FROM audit_log
            ORDER BY id
            """
        ).fetchall()


def assert_no_sensitive_audit_material(settings: Settings, *sensitive_values: str) -> None:
    rows = audit_rows(settings)
    serialized = "\n".join(
        json.dumps({"user_id": row[0], "event_type": row[1], "details": row[2]})
        for row in rows
    )
    for sensitive_value in sensitive_values:
        assert sensitive_value not in serialized


def test_registration_writes_account_created_and_invite_redeemed_audit_rows(tmp_path):
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
        )
        session_token = response.cookies["yomi_session"]

    rows = audit_rows(settings)
    event_types = [row[1] for row in rows]

    assert response.status_code == 200
    assert "account_created" in event_types
    assert "invite_redeemed" in event_types
    assert_no_sensitive_audit_material(
        settings,
        "register-password",
        session_token,
        invite_code,
    )


def test_login_success_and_failure_write_audit_rows_without_passwords(tmp_path):
    settings = make_settings(tmp_path)
    user = seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        failure = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )
        success = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        session_token = success.cookies["yomi_session"]

    rows = audit_rows(settings)
    events = [(row[0], row[1], json.loads(row[2])) for row in rows]

    assert failure.status_code == 401
    assert success.status_code == 200
    assert (user.id, "login_failure", {"username": "alice"}) in events
    assert (user.id, "login_success", {"username": "alice"}) in events
    assert_no_sensitive_audit_material(
        settings,
        "wrong-password",
        "correct-password",
        session_token,
    )


def test_logout_logout_everywhere_and_session_revoke_write_audit_rows(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings, username="alice", password="correct-password")
    app = create_app(settings)

    with TestClient(app) as client:
        first_login = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        first_token = first_login.cookies["yomi_session"]
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        client.get("/api/auth/sessions")
        revoke_target = first_token
        revoke_response = client.delete(f"/api/auth/sessions/{revoke_target}")
        logout_response = client.post("/api/auth/logout")

        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "correct-password"},
        )
        everywhere_response = client.post("/api/auth/logout-everywhere")

    event_types = [row[1] for row in audit_rows(settings)]

    assert revoke_response.status_code == 200
    assert logout_response.status_code == 200
    assert everywhere_response.status_code == 200
    assert "session_revoked" in event_types
    assert "logout" in event_types
    assert "logout_everywhere" in event_types
    assert_no_sensitive_audit_material(settings, first_token, revoke_target)
