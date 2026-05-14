"""Tests for POST /api/auth/change-password (M2.6).

Covers:
- Wrong current password is rejected (400).
- Missing session key (not logged in) is rejected (401).
- Successful change re-hashes password with Argon2id.
- Successful change generates a new enc_salt.
- Existing secrets are re-encrypted under the new key.
- Old derived key cannot decrypt secrets after change.
- Logging in with the new password can decrypt preserved secrets.
- Other sessions are revoked after password change.
- Current session remains valid after password change.
- Cache updated: old key evicted, new key active for current session.
- audit_log contains password_changed event.
- Audit rows contain no plaintext passwords.
- Transaction rollback on decryption failure preserves old secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.invites.repository import create_invite
from yomi.main import create_app
from yomi.security.crypto import decrypt, derive_key


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


def make_invite(settings: Settings) -> str:
    with open_user_db(settings.user_db_path) as conn:
        invite = create_invite(conn, created_by=None, is_admin_invite=False)
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
    password: str = "old-password",
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


def change_password(
    client: TestClient,
    *,
    current: str = "old-password",
    new: str = "new-password",
) -> "Response":
    return client.post(
        "/api/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=csrf_headers(client),
    )


def save_api_key(client: TestClient, *, provider: str, api_key: str) -> None:
    resp = client.post(
        "/api/settings/api-key",
        json={"provider": provider, "api_key": api_key},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200


def audit_event_types(settings: Settings) -> list[str]:
    with open_user_db(settings.user_db_path) as conn:
        rows = conn.execute("SELECT event_type FROM audit_log ORDER BY id").fetchall()
    return [row[0] for row in rows]


def all_audit_details_text(settings: Settings) -> str:
    with open_user_db(settings.user_db_path) as conn:
        rows = conn.execute("SELECT details FROM audit_log").fetchall()
    return " ".join(row[0] or "" for row in rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_change_password_wrong_current_password_returns_400(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)

    resp = change_password(client, current="wrong-password", new="new-password")
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


def test_change_password_requires_login(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    resp = change_password(client)
    assert resp.status_code == 401


def test_change_password_rehashes_password(tmp_path: Path) -> None:
    from yomi.security.passwords import verify_password

    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password="old-password")

    with open_user_db(settings.user_db_path) as conn:
        old_hash = conn.execute("SELECT password_hash FROM users").fetchone()[0]

    change_password(client, current="old-password", new="new-password")

    with open_user_db(settings.user_db_path) as conn:
        new_hash = conn.execute("SELECT password_hash FROM users").fetchone()[0]

    assert old_hash != new_hash
    assert verify_password("new-password", new_hash)
    assert not verify_password("old-password", new_hash)


def test_change_password_generates_new_enc_salt(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)

    with open_user_db(settings.user_db_path) as conn:
        old_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])

    change_password(client)

    with open_user_db(settings.user_db_path) as conn:
        new_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])

    assert old_salt != new_salt


def test_change_password_re_encrypts_existing_secrets(tmp_path: Path) -> None:
    api_key_value = "my-valuable-api-key"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password="old-password")
    save_api_key(client, provider="openai", api_key=api_key_value)

    with open_user_db(settings.user_db_path) as conn:
        before = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider='openai'"
        ).fetchone()

    change_password(client, current="old-password", new="new-password")

    with open_user_db(settings.user_db_path) as conn:
        after = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider='openai'"
        ).fetchone()

    # Row must still exist and have changed nonce/ciphertext
    assert after is not None
    assert bytes(after[0]) != bytes(before[0]) or bytes(after[1]) != bytes(before[1])


def test_old_derived_key_cannot_decrypt_after_password_change(tmp_path: Path) -> None:
    from cryptography.exceptions import InvalidTag

    password_old = "old-password"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password=password_old)

    with open_user_db(settings.user_db_path) as conn:
        old_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])

    old_derived_key = derive_key(password_old, old_salt)

    save_api_key(client, provider="openai", api_key="secret-value")
    change_password(client, current=password_old, new="new-password")

    with open_user_db(settings.user_db_path) as conn:
        row = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider='openai'"
        ).fetchone()

    nonce, ciphertext = bytes(row[0]), bytes(row[1])
    with pytest.raises(InvalidTag):
        decrypt(nonce, ciphertext, old_derived_key)


def test_new_login_can_decrypt_preserved_secrets(tmp_path: Path) -> None:
    api_key_value = "preserved-secret"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password="old-password")
    save_api_key(client, provider="openai", api_key=api_key_value)
    change_password(client, current="old-password", new="new-password")

    with open_user_db(settings.user_db_path) as conn:
        row = conn.execute(
            "SELECT nonce, ciphertext FROM user_secrets WHERE provider='openai'"
        ).fetchone()
        user_row = conn.execute("SELECT enc_salt FROM users").fetchone()

    nonce, ciphertext = bytes(row[0]), bytes(row[1])
    new_enc_salt = bytes(user_row[0])

    new_derived_key = derive_key("new-password", new_enc_salt)
    recovered = decrypt(nonce, ciphertext, new_derived_key)
    assert recovered == api_key_value


def test_change_password_invalidates_other_sessions(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)

    client1 = TestClient(app)
    client2 = TestClient(app)

    register_and_login(client1, settings, password="old-password")

    # Second login from a different client
    client2.post(
        "/api/auth/login",
        json={"username": "alice", "password": "old-password"},
        headers=csrf_headers(client2),
    )

    # client2 can reach /me before password change
    assert client2.get("/api/auth/me").status_code == 200

    change_password(client1, current="old-password", new="new-password")

    # client2's session is now revoked
    assert client2.get("/api/auth/me").status_code == 401


def test_current_session_remains_valid_after_password_change(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    change_password(client)

    resp = client.get("/api/auth/me")
    assert resp.status_code == 200


def test_cache_updated_correctly_after_password_change(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    app = create_app(settings)
    client = TestClient(app)

    register_and_login(client, settings, password="old-password")
    sid = client.cookies.get("yomi_session")

    old_key = app.state.session_key_cache.get(sid)
    assert old_key is not None

    change_password(client, current="old-password", new="new-password")

    new_key = app.state.session_key_cache.get(sid)
    assert new_key is not None
    assert new_key != old_key

    # New key must match derive_key(new_password, new_enc_salt)
    with open_user_db(settings.user_db_path) as conn:
        enc_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])

    expected = derive_key("new-password", enc_salt)
    assert new_key == expected


def test_audit_log_contains_password_changed_event(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    change_password(client)

    assert "password_changed" in audit_event_types(settings)


def test_audit_rows_contain_no_plaintext_passwords(tmp_path: Path) -> None:
    old_pass = "old-password"
    new_pass = "new-password"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password=old_pass)
    change_password(client, current=old_pass, new=new_pass)

    combined = all_audit_details_text(settings)
    assert old_pass not in combined
    assert new_pass not in combined


def test_audit_rows_contain_no_plaintext_api_key(tmp_path: Path) -> None:
    api_key_value = "audit-api-key-sentinel"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings)
    save_api_key(client, provider="openai", api_key=api_key_value)
    change_password(client)

    combined = all_audit_details_text(settings)
    assert api_key_value not in combined


def test_failed_re_encryption_preserves_old_secrets(tmp_path: Path) -> None:
    """If decryption fails mid-change, the transaction rolls back and old secrets survive."""
    api_key_value = "must-survive"
    settings = make_settings(tmp_path)
    initialize_user_db(settings.user_db_path)
    client = TestClient(create_app(settings))

    register_and_login(client, settings, password="old-password")
    save_api_key(client, provider="openai", api_key=api_key_value)

    with open_user_db(settings.user_db_path) as conn:
        original_nonce = bytes(
            conn.execute(
                "SELECT nonce FROM user_secrets WHERE provider='openai'"
            ).fetchone()[0]
        )
        original_hash = str(
            conn.execute("SELECT password_hash FROM users").fetchone()[0]
        )
        original_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])

    # Simulate a failure during re-encryption by patching encrypt_secret to raise
    with patch("yomi.auth.router.encrypt_secret", side_effect=RuntimeError("injected")):
        resp = change_password(client, current="old-password", new="new-password")

    assert resp.status_code == 500

    # Old state must be intact
    with open_user_db(settings.user_db_path) as conn:
        current_hash = str(conn.execute("SELECT password_hash FROM users").fetchone()[0])
        current_salt = bytes(conn.execute("SELECT enc_salt FROM users").fetchone()[0])
        current_nonce = bytes(
            conn.execute(
                "SELECT nonce FROM user_secrets WHERE provider='openai'"
            ).fetchone()[0]
        )

    assert current_hash == original_hash
    assert current_salt == original_salt
    assert current_nonce == original_nonce
