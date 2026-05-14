"""Tests for encrypted API key storage (M2.6).

Covers:
- Stored rows contain only nonce + ciphertext, never plaintext.
- Stored ciphertext is decryptable with the session-derived key.
- Wrong key cannot decrypt (AESGCM raises InvalidTag).
- Another user cannot delete the current user's key.
- Deleting a key affects only the specified user + provider.
- Status endpoint returns provider list, no secret material.
- Logout drops the session key from the cache.
- Logout-everywhere drops all affected session keys from the cache.
- No audit row contains plaintext API key material.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.invites.repository import create_invite
from yomi.main import create_app
from yomi.security.crypto import derive_key, decrypt


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        user_db_path=tmp_path / "user.db",
        content_db_path=tmp_path / "content.db",
        behind_https=False,
        base_url="http://localhost",
        log_level="ERROR",
    )


def seed_user(
    settings: Settings,
    *,
    username: str = "alice",
    password: str = "correct-password",
) -> None:
    from yomi.users.repository import create_user

    with open_user_db(settings.user_db_path) as conn:
        create_user(conn, username=username, display_name=username, password=password)
        conn.commit()


def make_invite(settings: Settings, *, is_admin: bool = False) -> str:
    with open_user_db(settings.user_db_path) as conn:
        invite = create_invite(conn, created_by=None, is_admin_invite=is_admin)
        conn.commit()
    return invite.code


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/auth/csrf-token")
    token = response.json()["data"]["csrf_token"]
    return {"X-CSRF-Token": token}


def register_and_login(
    client: TestClient,
    settings: Settings,
    *,
    username: str = "alice",
    password: str = "correct-password",
) -> None:
    invite_code = make_invite(settings)
    client.post(
        "/api/auth/register",
        json={
            "invite_code": invite_code,
            "username": username,
            "display_name": username,
            "password": password,
        },
        headers=csrf_headers(client),
    )


def login(
    client: TestClient,
    *,
    username: str = "alice",
    password: str = "correct-password",
) -> None:
    client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers=csrf_headers(client),
    )


def audit_events(settings: Settings) -> list[dict]:
    with open_user_db(settings.user_db_path) as conn:
        rows = conn.execute(
            "SELECT event_type, details FROM audit_log ORDER BY id"
        ).fetchall()
    return [
        {"event_type": row[0], "details": json.loads(row[1]) if row[1] else {}}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_api_key_stores_nonce_and_ciphertext_only(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)

    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "sk-supersecret"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200

    with open_user_db(settings.user_db_path) as conn:
        row = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider = 'openai'"
        ).fetchone()

    assert row is not None
    nonce, ciphertext = bytes(row[0]), bytes(row[1])
    assert len(nonce) == 12  # AES-GCM nonce
    assert b"sk-supersecret" not in ciphertext
    assert b"sk-supersecret" not in nonce


def test_raw_sqlite_row_does_not_contain_plaintext_api_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    client.post(
        "/api/settings/api-key",
        json={"provider": "anthropic", "api_key": "plaintext-key-check"},
        headers=csrf_headers(client),
    )

    # Dump entire user_secrets table as raw bytes
    with open_user_db(settings.user_db_path) as conn:
        rows = conn.execute(
            "SELECT provider, nonce, ciphertext FROM user_secrets"
        ).fetchall()

    for _, nonce, ciphertext in rows:
        combined = bytes(nonce) + bytes(ciphertext)
        assert b"plaintext-key-check" not in combined


def test_encrypted_key_decryptable_with_session_derived_key(tmp_path: Path) -> None:
    plaintext_key = "sk-real-api-key-xyz"
    password = "correct-password"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password=password)
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": plaintext_key},
        headers=csrf_headers(client),
    )

    with open_user_db(settings.user_db_path) as conn:
        row = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider = 'openai'"
        ).fetchone()
        user_row = conn.execute(
            "SELECT enc_salt FROM users WHERE username = 'alice'"
        ).fetchone()

    nonce, ciphertext = bytes(row[0]), bytes(row[1])
    enc_salt = bytes(user_row[0])

    derived = derive_key(password, enc_salt)
    recovered = decrypt(nonce, ciphertext, derived)
    assert recovered == plaintext_key


def test_wrong_key_cannot_decrypt_stored_secret(tmp_path: Path) -> None:
    from cryptography.exceptions import InvalidTag

    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "real-secret"},
        headers=csrf_headers(client),
    )

    with open_user_db(settings.user_db_path) as conn:
        row = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider = 'openai'"
        ).fetchone()

    nonce, ciphertext = bytes(row[0]), bytes(row[1])
    wrong_key = b"\x00" * 32
    with pytest.raises(InvalidTag):
        decrypt(nonce, ciphertext, wrong_key)


def test_another_user_cannot_delete_current_users_api_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)

    alice_client = TestClient(create_app(settings))
    bob_client = TestClient(create_app(settings))

    register_and_login(alice_client, settings, username="alice")
    register_and_login(bob_client, settings, username="bob")

    # Alice saves a key
    alice_client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "alice-key"},
        headers=csrf_headers(alice_client),
    )

    # Bob tries to delete it
    resp = bob_client.delete(
        "/api/settings/api-key/openai",
        headers=csrf_headers(bob_client),
    )
    assert resp.status_code == 404

    # Alice's key still exists
    with open_user_db(settings.user_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM user_secrets WHERE provider = 'openai'"
        ).fetchone()[0]
    assert count == 1


def test_delete_api_key_affects_only_current_user_and_provider(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)

    # Save two keys
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "key-a"},
        headers=csrf_headers(client),
    )
    client.post(
        "/api/settings/api-key",
        json={"provider": "anthropic", "api_key": "key-b"},
        headers=csrf_headers(client),
    )

    # Delete only openai
    resp = client.delete(
        "/api/settings/api-key/openai",
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200

    with open_user_db(settings.user_db_path) as conn:
        providers = [
            row[0]
            for row in conn.execute(
                "SELECT provider FROM user_secrets ORDER BY provider"
            ).fetchall()
        ]
    assert providers == ["anthropic"]


def test_api_key_status_returns_provider_list_without_secret_material(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "should-not-appear"},
        headers=csrf_headers(client),
    )

    resp = client.get("/api/settings/api-key/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "providers" in data
    assert data["providers"] == ["openai"]

    # Confirm no secret values leaked
    body = resp.text
    assert "should-not-appear" not in body
    assert "nonce" not in body
    assert "ciphertext" not in body


def test_logout_drops_session_key_from_cache(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)
    client = TestClient(app)

    register_and_login(client, settings)

    # Grab session id from cookie
    session_id = client.cookies.get("yomi_session")
    assert session_id is not None
    assert app.state.session_key_cache.get(session_id) is not None

    client.post("/api/auth/logout", headers=csrf_headers(client))

    assert app.state.session_key_cache.get(session_id) is None


def test_logout_everywhere_drops_all_session_keys_from_cache(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)

    client1 = TestClient(app)
    client2 = TestClient(app)

    register_and_login(client1, settings)
    sid1 = client1.cookies.get("yomi_session")

    # Login from a second client (same user)
    login(client2, username="alice")
    sid2 = client2.cookies.get("yomi_session")

    assert app.state.session_key_cache.get(sid1) is not None
    assert app.state.session_key_cache.get(sid2) is not None

    # Logout everywhere from client1
    client1.post("/api/auth/logout-everywhere", headers=csrf_headers(client1))

    assert app.state.session_key_cache.get(sid1) is None
    assert app.state.session_key_cache.get(sid2) is None


def test_delete_session_drops_that_sessions_cache_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)

    client1 = TestClient(app)
    client2 = TestClient(app)

    register_and_login(client1, settings)
    sid1 = client1.cookies.get("yomi_session")

    login(client2, username="alice")
    sid2 = client2.cookies.get("yomi_session")

    # Client1 deletes client2's session
    resp = client1.delete(
        f"/api/auth/sessions/{sid2}",
        headers=csrf_headers(client1),
    )
    assert resp.status_code == 200

    # sid1 cache key still exists, sid2 is gone
    assert app.state.session_key_cache.get(sid1) is not None
    assert app.state.session_key_cache.get(sid2) is None


def test_no_audit_row_contains_plaintext_api_key(tmp_path: Path) -> None:
    api_key_value = "sk-audit-leak-check"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": api_key_value},
        headers=csrf_headers(client),
    )

    with open_user_db(settings.user_db_path) as conn:
        rows = conn.execute("SELECT details FROM audit_log").fetchall()

    for (details_str,) in rows:
        if details_str:
            assert api_key_value not in details_str


def test_save_api_key_requires_active_session_key_in_cache(tmp_path: Path) -> None:
    """Accessing /api/settings/api-key without an active session returns 401."""
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    # Not logged in — no session, no cache key
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": "openai", "api_key": "key"},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 401
