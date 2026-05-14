"""Tests for SRS API routes (M3.4)."""

from __future__ import annotations

import datetime
import sqlite3

import pytest
from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
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


def seed_user(
    settings: Settings,
    *,
    username: str = "alice",
    password: str = "alicepass",
    is_admin: bool = False,
):
    initialize_user_db(settings.user_db_path)
    with open_user_db(settings.user_db_path) as conn:
        user = create_user(
            conn,
            username=username,
            display_name=username.title(),
            password=password,
            is_admin=is_admin,
        )
        conn.commit()
        return user


def login(
    client: TestClient,
    username: str = "alice",
    password: str = "alicepass",
) -> None:
    r = client.get("/api/auth/csrf-token")
    csrf = r.json()["data"]["csrf_token"]
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"


def csrf_headers(client: TestClient) -> dict[str, str]:
    r = client.get("/api/auth/csrf-token")
    return {"X-CSRF-Token": r.json()["data"]["csrf_token"]}


def create_card_via_api(
    client: TestClient,
    *,
    content_id: int = 1,
    content_table: str = "grammar_points",
    card_type: str = "grammar_recognition",
) -> dict:
    headers = csrf_headers(client)
    r = client.post(
        "/api/srs/cards",
        json={"content_id": content_id, "content_table": content_table, "card_type": card_type},
        headers=headers,
    )
    assert r.status_code == 200, f"Card creation failed: {r.json()}"
    return r.json()["data"]


# ---------------------------------------------------------------------------
# Card creation tests
# ---------------------------------------------------------------------------


class TestCreateCard:
    def test_creates_card_for_authenticated_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            data = create_card_via_api(client)
        assert data["card_type"] == "grammar_recognition"
        assert data["content_id"] == 1
        assert data["content_table"] == "grammar_points"
        assert data["state"] == "New"
        assert data["suspended"] is False
        assert data["due"] is not None

    def test_card_stored_with_current_user_id(self, tmp_path):
        settings = make_settings(tmp_path)
        user = seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            data = create_card_via_api(client)
        assert data["user_id"] == user.id

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/cards",
                json={"content_id": 1, "content_table": "grammar_points", "card_type": "vocab_reading"},
                headers=headers,
            )
        assert r.status_code == 401

    def test_requires_csrf(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.post(
                "/api/srs/cards",
                json={"content_id": 1, "content_table": "grammar_points", "card_type": "vocab_reading"},
            )
        assert r.status_code == 403

    def test_due_is_set_to_now(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        before = datetime.datetime.now(datetime.timezone.utc)
        with TestClient(app) as client:
            login(client)
            data = create_card_via_api(client)
        after = datetime.datetime.now(datetime.timezone.utc)
        due = datetime.datetime.fromisoformat(data["due"])
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        assert before <= due <= after


# ---------------------------------------------------------------------------
# Due cards tests
# ---------------------------------------------------------------------------


class TestDueCards:
    def test_returns_due_cards_for_authenticated_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            create_card_via_api(client)
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["state"] == "New"

    def test_excludes_suspended_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            # Suspend the card directly in DB
            with open_user_db(settings.user_db_path) as conn:
                conn.execute("UPDATE srs_cards SET suspended=1 WHERE id=?", (card["id"],))
                conn.commit()
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_excludes_future_due_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            # Push due into the future
            future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).isoformat()
            with open_user_db(settings.user_db_path) as conn:
                conn.execute("UPDATE srs_cards SET due=? WHERE id=?", (future, card["id"]))
                conn.commit()
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_excludes_other_users_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings, username="alice", password="alicepass")
        seed_user(settings, username="bob", password="bobpass")
        app = create_app(settings)
        with TestClient(app) as client:
            # Bob creates a card
            login(client, "bob", "bobpass")
            create_card_via_api(client)
            # Alice checks due — should see 0
            client.post(
                "/api/auth/logout",
                headers=csrf_headers(client),
            )
            login(client, "alice", "alicepass")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/srs/due")
        assert r.status_code == 401

    def test_ordered_by_due_ascending(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            c1 = create_card_via_api(client, content_id=1)
            c2 = create_card_via_api(client, content_id=2)
            # Make c2 due earlier
            past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
            with open_user_db(settings.user_db_path) as conn:
                conn.execute("UPDATE srs_cards SET due=? WHERE id=?", (past, c2["id"]))
                conn.commit()
            r = client.get("/api/srs/due")
        data = r.json()["data"]
        assert len(data) == 2
        due_times = [data[0]["due"], data[1]["due"]]
        assert due_times[0] <= due_times[1]


# ---------------------------------------------------------------------------
# Review submission tests
# ---------------------------------------------------------------------------


class TestSubmitReview:
    def test_review_updates_fsrs_state(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
                headers=headers,
            )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["card_id"] == card["id"]
        # After any review, state transitions from New
        assert data["state"] in ("Learning", "Review", "Relearning")
        assert data["due"] is not None

    def test_review_updates_stability_and_difficulty(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
                headers=headers,
            )
        data = r.json()["data"]
        assert data["stability"] is not None
        assert data["difficulty"] is not None

    def test_review_writes_review_history_row(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
                headers=headers,
            )
        with open_user_db(settings.user_db_path) as conn:
            rows = conn.execute(
                "SELECT rating, state_before FROM review_history WHERE card_id=?",
                (card["id"],),
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 3  # rating=Good
        assert rows[0][1] == "New"  # state_before was New

    def test_review_upserts_daily_activity(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
                headers=headers,
            )
            # Second review on same card (create another card first for variety)
            card2 = create_card_via_api(client, content_id=2)
            headers2 = csrf_headers(client)
            client.post(
                "/api/srs/review",
                json={"card_id": card2["id"], "rating": 2},
                headers=headers2,
            )
        today = datetime.date.today().isoformat()
        with open_user_db(settings.user_db_path) as conn:
            row = conn.execute(
                "SELECT reviews_done FROM daily_activity WHERE user_id=? AND date=?",
                # user_id can be fetched from the card
                (1, today),
            ).fetchone()
        assert row is not None
        assert row[0] == 2

    def test_review_persists_card_state_to_db(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 4},
                headers=headers,
            )
        returned_state = r.json()["data"]["state"]
        with open_user_db(settings.user_db_path) as conn:
            db_state = conn.execute(
                "SELECT state FROM srs_cards WHERE id=?", (card["id"],)
            ).fetchone()[0]
        assert db_state == returned_state

    def test_review_due_date_advances(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            original_due = card["due"]
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 4},
                headers=headers,
            )
        new_due = r.json()["data"]["due"]
        orig_dt = datetime.datetime.fromisoformat(original_due)
        new_dt = datetime.datetime.fromisoformat(new_due)
        if orig_dt.tzinfo is None:
            orig_dt = orig_dt.replace(tzinfo=datetime.timezone.utc)
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=datetime.timezone.utc)
        # Easy rating (4) should push due far into the future
        assert new_dt > orig_dt

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": 1, "rating": 3},
                headers=headers,
            )
        assert r.status_code == 401

    def test_requires_csrf(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
            )
        assert r.status_code == 403

    def test_unknown_card_returns_404(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": 99999, "rating": 3},
                headers=headers,
            )
        assert r.status_code == 404

    def test_invalid_rating_rejected(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 5},
                headers=headers,
            )
        assert r.status_code == 422

    def test_rating_zero_rejected(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 0},
                headers=headers,
            )
        assert r.status_code == 422

    def test_all_four_ratings_accepted(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            for rating in (1, 2, 3, 4):
                card = create_card_via_api(client, content_id=rating)
                headers = csrf_headers(client)
                r = client.post(
                    "/api/srs/review",
                    json={"card_id": card["id"], "rating": rating},
                    headers=headers,
                )
                assert r.status_code == 200, f"rating {rating} failed: {r.json()}"


# ---------------------------------------------------------------------------
# Cross-user isolation tests (CRITICAL)
# ---------------------------------------------------------------------------


class TestCrossUserIsolation:
    def test_user_cannot_review_another_users_card(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings, username="alice", password="alicepass")
        seed_user(settings, username="bob", password="bobpass")
        app = create_app(settings)
        with TestClient(app) as client:
            # Alice creates a card
            login(client, "alice", "alicepass")
            alice_card = create_card_via_api(client)
            # Switch to Bob
            client.post("/api/auth/logout", headers=csrf_headers(client))
            login(client, "bob", "bobpass")
            headers = csrf_headers(client)
            r = client.post(
                "/api/srs/review",
                json={"card_id": alice_card["id"], "rating": 3},
                headers=headers,
            )
        assert r.status_code == 404

    def test_user_cannot_see_another_users_due_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings, username="alice", password="alicepass")
        seed_user(settings, username="bob", password="bobpass")
        app = create_app(settings)
        with TestClient(app) as client:
            # Alice creates 3 cards
            login(client, "alice", "alicepass")
            for i in range(3):
                create_card_via_api(client, content_id=i + 1)
            # Bob checks due
            client.post("/api/auth/logout", headers=csrf_headers(client))
            login(client, "bob", "bobpass")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_review_history_scoped_to_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings, username="alice", password="alicepass")
        seed_user(settings, username="bob", password="bobpass")
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            alice_card = create_card_via_api(client)
            headers = csrf_headers(client)
            client.post(
                "/api/srs/review",
                json={"card_id": alice_card["id"], "rating": 3},
                headers=headers,
            )
            # Bob has no review history
            client.post("/api/auth/logout", headers=csrf_headers(client))
            login(client, "bob", "bobpass")

        # Directly verify review_history user_id matches Alice's user_id
        with open_user_db(settings.user_db_path) as conn:
            history_user_ids = {
                r[0]
                for r in conn.execute("SELECT DISTINCT user_id FROM review_history").fetchall()
            }
            alice_id = conn.execute(
                "SELECT id FROM users WHERE username='alice'"
            ).fetchone()[0]
        assert history_user_ids == {alice_id}

    def test_daily_activity_scoped_to_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings, username="alice", password="alicepass")
        seed_user(settings, username="bob", password="bobpass")
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            card = create_card_via_api(client)
            headers = csrf_headers(client)
            client.post(
                "/api/srs/review",
                json={"card_id": card["id"], "rating": 3},
                headers=headers,
            )

        today = datetime.date.today().isoformat()
        with open_user_db(settings.user_db_path) as conn:
            alice_id = conn.execute(
                "SELECT id FROM users WHERE username='alice'"
            ).fetchone()[0]
            bob_id = conn.execute(
                "SELECT id FROM users WHERE username='bob'"
            ).fetchone()[0]
            alice_activity = conn.execute(
                "SELECT reviews_done FROM daily_activity WHERE user_id=? AND date=?",
                (alice_id, today),
            ).fetchone()
            bob_activity = conn.execute(
                "SELECT reviews_done FROM daily_activity WHERE user_id=? AND date=?",
                (bob_id, today),
            ).fetchone()
        assert alice_activity is not None and alice_activity[0] == 1
        assert bob_activity is None
