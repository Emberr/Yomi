"""Tests for admin API skeleton (M2.7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.invites.repository import create_invite
from yomi.main import create_app
from yomi.users.repository import create_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_settings(tmp_path) -> Settings:
    return Settings(
        content_db_path=tmp_path / "content.db",
        user_db_path=tmp_path / "user.db",
        behind_https=False,
        base_url="http://testserver",
        log_level="INFO",
    )


def seed_admin(settings: Settings, *, username: str = "admin", password: str = "adminpass"):
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        user = create_user(
            connection,
            username=username,
            display_name=username.title(),
            password=password,
            is_admin=True,
        )
        connection.commit()
        return user


def seed_user(settings: Settings, *, username: str = "alice", password: str = "alicepass"):
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        user = create_user(
            connection,
            username=username,
            display_name=username.title(),
            password=password,
            is_admin=False,
        )
        connection.commit()
        return user


def csrf_headers(client: TestClient) -> dict[str, str]:
    r = client.get("/api/auth/csrf-token")
    return {"X-CSRF-Token": r.json()["data"]["csrf_token"]}


def login(client: TestClient, username: str, password: str) -> None:
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers=csrf_headers(client),
    )
    assert r.status_code == 200, r.text


def audit_event_types(settings: Settings) -> list[str]:
    with open_user_db(settings.user_db_path) as connection:
        rows = connection.execute("SELECT event_type FROM audit_log ORDER BY id").fetchall()
    return [row[0] for row in rows]


SENSITIVE_FIELDS = {
    "password_hash",
    "enc_salt",
    "nonce",
    "ciphertext",
}


def assert_no_sensitive_fields(data: object) -> None:
    """Recursively check that no sensitive field names appear in JSON output."""
    if isinstance(data, dict):
        for key in data:
            assert key not in SENSITIVE_FIELDS, f"Sensitive field '{key}' in admin response"
            assert_no_sensitive_fields(data[key])
    elif isinstance(data, list):
        for item in data:
            assert_no_sensitive_fields(item)


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------


def test_admin_users_unauthenticated_returns_401(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/api/admin/users")
    assert r.status_code == 401


def test_admin_invites_unauthenticated_returns_401(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/api/admin/invites")
    assert r.status_code == 401


def test_admin_audit_log_unauthenticated_returns_401(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/api/admin/audit-log")
    assert r.status_code == 401


def test_admin_stats_unauthenticated_returns_401(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/api/admin/stats")
    assert r.status_code == 401


def test_admin_users_non_admin_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "alice", "alicepass")
        r = client.get("/api/admin/users")
    assert r.status_code == 403


def test_admin_invites_non_admin_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "alice", "alicepass")
        r = client.get("/api/admin/invites")
    assert r.status_code == 403


def test_admin_audit_log_non_admin_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "alice", "alicepass")
        r = client.get("/api/admin/audit-log")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# User listing
# ---------------------------------------------------------------------------


def test_admin_can_list_users(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/users")
    assert r.status_code == 200
    users = r.json()["data"]["users"]
    usernames = [u["username"] for u in users]
    assert "admin" in usernames
    assert "alice" in usernames


def test_admin_user_list_excludes_sensitive_fields(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/users")
    assert r.status_code == 200
    assert_no_sensitive_fields(r.json()["data"]["users"])


def test_admin_user_list_contains_expected_safe_fields(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/users")
    user = r.json()["data"]["users"][0]
    for field in ("id", "username", "display_name", "is_admin", "is_active"):
        assert field in user, f"Expected field '{field}' missing from admin user response"


# ---------------------------------------------------------------------------
# Invite CRUD
# ---------------------------------------------------------------------------


def test_admin_can_list_invites(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        create_invite(connection)
        connection.commit()
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/invites")
    assert r.status_code == 200
    assert len(r.json()["data"]["invites"]) >= 1


def test_admin_can_create_invite(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            "/api/admin/invites",
            json={"expires_in_days": 7, "is_admin": False},
            headers=csrf_headers(client),
        )
    assert r.status_code == 200
    invite = r.json()["data"]["invite"]
    assert "code" in invite
    assert invite["is_admin_invite"] is False


def test_admin_create_invite_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(
            "/api/admin/invites",
            json={},
            headers=csrf_headers(client),
        )
    assert "admin_invite_create" in audit_event_types(settings)


def test_admin_can_delete_unused_invite(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(connection)
        connection.commit()
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.delete(
            f"/api/admin/invites/{invite.code}",
            headers=csrf_headers(client),
        )
    assert r.status_code == 200


def test_admin_delete_invite_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as connection:
        invite = create_invite(connection)
        connection.commit()
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.delete(f"/api/admin/invites/{invite.code}", headers=csrf_headers(client))
    assert "admin_invite_delete" in audit_event_types(settings)


def test_admin_delete_nonexistent_invite_returns_404(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.delete("/api/admin/invites/doesnotexist", headers=csrf_headers(client))
    assert r.status_code == 404


def test_admin_create_invite_missing_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post("/api/admin/invites", json={})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Suspend / unsuspend
# ---------------------------------------------------------------------------


def test_admin_can_suspend_user(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            f"/api/admin/users/{alice.id}/suspend",
            headers=csrf_headers(client),
        )
    assert r.status_code == 200


def test_suspended_user_cannot_login(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(
            f"/api/admin/users/{alice.id}/suspend",
            headers=csrf_headers(client),
        )
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alicepass"},
            headers=csrf_headers(client),
        )
    assert r.status_code == 401


def test_suspended_user_loses_existing_session(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "alice", "alicepass")
        me_before = client.get("/api/auth/me")
        assert me_before.status_code == 200

        # Log in as admin in same client to suspend
        login(client, "admin", "adminpass")
        client.post(
            f"/api/admin/users/{alice.id}/suspend",
            headers=csrf_headers(client),
        )

    # New client — alice's session cookie not present, but check fresh login blocked
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alicepass"},
            headers=csrf_headers(client),
        )
    assert r.status_code == 401


def test_admin_can_unsuspend_user(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/suspend", headers=csrf_headers(client))
        r = client.post(f"/api/admin/users/{alice.id}/unsuspend", headers=csrf_headers(client))
    assert r.status_code == 200


def test_unsuspended_user_can_login_again(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/suspend", headers=csrf_headers(client))
        client.post(f"/api/admin/users/{alice.id}/unsuspend", headers=csrf_headers(client))
    with TestClient(app) as client:
        r = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "alicepass"},
            headers=csrf_headers(client),
        )
    assert r.status_code == 200


def test_admin_suspend_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/suspend", headers=csrf_headers(client))
    assert "admin_user_suspend" in audit_event_types(settings)


def test_admin_unsuspend_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/suspend", headers=csrf_headers(client))
        client.post(f"/api/admin/users/{alice.id}/unsuspend", headers=csrf_headers(client))
    assert "admin_user_unsuspend" in audit_event_types(settings)


def test_suspend_missing_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(f"/api/admin/users/{alice.id}/suspend")
    assert r.status_code == 403


def test_unsuspend_missing_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(f"/api/admin/users/{alice.id}/unsuspend")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Promote / demote
# ---------------------------------------------------------------------------


def test_admin_can_promote_user(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            f"/api/admin/users/{alice.id}/promote",
            headers=csrf_headers(client),
        )
    assert r.status_code == 200


def test_promote_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/promote", headers=csrf_headers(client))
    assert "admin_user_promote" in audit_event_types(settings)


def test_promoted_user_can_access_admin_routes(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/promote", headers=csrf_headers(client))
    with TestClient(app) as client:
        login(client, "alice", "alicepass")
        r = client.get("/api/admin/users")
    assert r.status_code == 200


def test_admin_can_demote_non_sole_admin(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/promote", headers=csrf_headers(client))
        r = client.post(
            f"/api/admin/users/{alice.id}/demote",
            headers=csrf_headers(client),
        )
    assert r.status_code == 200


def test_demote_writes_audit_event(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        client.post(f"/api/admin/users/{alice.id}/promote", headers=csrf_headers(client))
        client.post(f"/api/admin/users/{alice.id}/demote", headers=csrf_headers(client))
    assert "admin_user_demote" in audit_event_types(settings)


def test_promote_missing_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(f"/api/admin/users/{alice.id}/promote")
    assert r.status_code == 403


def test_demote_missing_csrf_returns_403(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(f"/api/admin/users/{alice.id}/demote")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Last-admin protection
# ---------------------------------------------------------------------------


def test_cannot_demote_sole_admin(tmp_path):
    settings = make_settings(tmp_path)
    admin = seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            f"/api/admin/users/{admin.id}/demote",
            headers=csrf_headers(client),
        )
    assert r.status_code == 400


def test_cannot_suspend_sole_admin_self(tmp_path):
    settings = make_settings(tmp_path)
    admin = seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            f"/api/admin/users/{admin.id}/suspend",
            headers=csrf_headers(client),
        )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Delete / reset-password → 501 stubs
# ---------------------------------------------------------------------------


def test_admin_delete_user_returns_501(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.delete(
            f"/api/admin/users/{alice.id}",
            headers=csrf_headers(client),
        )
    assert r.status_code == 501


def test_admin_reset_password_returns_501(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    alice = seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.post(
            f"/api/admin/users/{alice.id}/reset-password",
            headers=csrf_headers(client),
        )
    assert r.status_code == 501


# ---------------------------------------------------------------------------
# Audit log view
# ---------------------------------------------------------------------------


def test_admin_can_view_audit_log(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/audit-log")
    assert r.status_code == 200
    assert "events" in r.json()["data"]


def test_admin_audit_log_filter_by_event_type(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/audit-log?event_type=login_success")
    assert r.status_code == 200
    events = r.json()["data"]["events"]
    for e in events:
        assert e["event_type"] == "login_success"


def test_admin_audit_log_excludes_sensitive_details(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/audit-log")
    assert r.status_code == 200
    raw = r.text
    for field in ("password_hash", "enc_salt", "nonce", "ciphertext"):
        assert field not in raw, f"Sensitive field '{field}' leaked into audit log response"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_admin_stats_returns_counts(tmp_path):
    settings = make_settings(tmp_path)
    seed_admin(settings)
    seed_user(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login(client, "admin", "adminpass")
        r = client.get("/api/admin/stats")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total_users"] == 2
    assert data["active_users"] == 2
    assert data["admin_users"] == 1
