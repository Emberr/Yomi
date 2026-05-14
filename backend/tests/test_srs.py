"""Tests for SRS API routes (M3.4 + M3.5 enrichment)."""

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


def seed_minimal_content_db(path) -> None:
    """Create minimal content.db with grammar_points and vocab_items tables."""
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO content_metadata (key, value) VALUES ('schema_version', '2');

            CREATE TABLE IF NOT EXISTS grammar_points (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                jlpt_level TEXT NOT NULL,
                jlpt_source TEXT NOT NULL DEFAULT '',
                short_desc TEXT NOT NULL DEFAULT '',
                long_desc TEXT NOT NULL DEFAULT '',
                formation_pattern TEXT NOT NULL DEFAULT '',
                common_mistakes TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0,
                source_file TEXT NOT NULL DEFAULT ''
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS grammar_fts
                USING fts5(title, short_desc, content='grammar_points', content_rowid='id');

            CREATE TABLE IF NOT EXISTS example_sentences (
                id INTEGER PRIMARY KEY,
                grammar_id INTEGER NOT NULL REFERENCES grammar_points(id),
                japanese TEXT NOT NULL,
                reading TEXT NOT NULL DEFAULT '',
                translation TEXT NOT NULL DEFAULT '',
                audio_url TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS vocab_items (
                id INTEGER PRIMARY KEY,
                jmdict_id TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                jlpt_level TEXT,
                jlpt_source TEXT NOT NULL DEFAULT '',
                kanji_forms TEXT NOT NULL DEFAULT '[]',
                reading_forms TEXT NOT NULL DEFAULT '[]',
                meanings TEXT NOT NULL DEFAULT '[]',
                pos_tags TEXT NOT NULL DEFAULT '[]',
                frequency INTEGER
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS vocab_fts
                USING fts5(kanji_forms, reading_forms, meanings,
                           content='vocab_items', content_rowid='id');

            INSERT INTO grammar_points
                (id, slug, title, jlpt_level, jlpt_source, short_desc, long_desc,
                 formation_pattern, common_mistakes, tags, sort_order, source_file)
            VALUES
                (1, 'te-kudasai', '〜てください', 'N5', 'hanabira', 'Politely request.',
                 'Used to make polite requests.', 'Verb て-form + ください', '',
                 '["request"]', 1, 'n5.json'),
                (2, 'ga-arimasu', '〜があります', 'N5', 'hanabira', 'There is (inanimate).',
                 'Expresses existence.', 'Noun + があります', '',
                 '["existence"]', 2, 'n5.json');

            INSERT INTO grammar_fts (rowid, title, short_desc)
            SELECT id, title, short_desc FROM grammar_points;

            INSERT INTO example_sentences
                (grammar_id, japanese, reading, translation, audio_url, tags)
            VALUES
                (1, 'ここに座ってください。', 'ここにすわってください。', 'Please sit here.', '', '[]'),
                (1, '静かにしてください。', 'しずかにしてください。', 'Please be quiet.', '', '[]');

            INSERT INTO vocab_items
                (id, jmdict_id, slug, jlpt_level, jlpt_source,
                 kanji_forms, reading_forms, meanings, pos_tags, frequency)
            VALUES
                (1, '1000040', 'taberu-1000040', 'N5', 'jmdict',
                 '["食べる"]', '["たべる"]', '["to eat"]', '["v1"]', 9800),
                (2, '1000050', 'nomu-1000050', 'N5', 'jmdict',
                 '["飲む"]', '["のむ"]', '["to drink","to swallow"]', '["v5m"]', 9500);

            INSERT INTO vocab_fts (rowid, kanji_forms, reading_forms, meanings)
            SELECT id, kanji_forms, reading_forms, meanings FROM vocab_items;
        """)
        conn.commit()


def seed_user(
    settings: Settings,
    *,
    username: str = "alice",
    password: str = "alicepass",
    is_admin: bool = False,
):
    if not settings.content_db_path.exists():
        seed_minimal_content_db(settings.content_db_path)
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


# ---------------------------------------------------------------------------
# Due-card enrichment tests (M3.5)
# ---------------------------------------------------------------------------


class TestDueCardEnrichment:
    def test_grammar_card_due_response_includes_display_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # Create card referencing grammar_points id=1 (seeded: '〜てください')
            create_card_via_api(client, content_id=1, content_table="grammar_points")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        card = data[0]
        assert card["display_prompt"] == "〜てください"
        assert card["display_answer"] == "Politely request."

    def test_grammar_card_due_response_includes_formation(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            create_card_via_api(client, content_id=1, content_table="grammar_points")
            r = client.get("/api/srs/due")
        card = r.json()["data"][0]
        assert card["display_formation"] == "Verb て-form + ください"

    def test_grammar_card_due_response_includes_example_sentences(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            create_card_via_api(client, content_id=1, content_table="grammar_points")
            r = client.get("/api/srs/due")
        card = r.json()["data"][0]
        sentences = card["display_sentences"]
        assert sentences is not None
        assert len(sentences) == 2
        assert sentences[0]["japanese"] == "ここに座ってください。"
        assert sentences[0]["reading"] == "ここにすわってください。"
        assert sentences[0]["translation"] == "Please sit here."

    def test_vocab_card_due_response_includes_display_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # Create card referencing vocab_items id=1 (seeded: 食べる)
            create_card_via_api(client, content_id=1, content_table="vocab_items", card_type="vocab_reading")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        card = data[0]
        assert card["display_prompt"] == "食べる"
        assert card["display_answer"] == "to eat"

    def test_vocab_card_due_response_includes_readings(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            create_card_via_api(client, content_id=1, content_table="vocab_items", card_type="vocab_reading")
            r = client.get("/api/srs/due")
        card = r.json()["data"][0]
        assert card["display_readings"] == ["たべる"]

    def test_vocab_card_multiple_meanings_joined(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # vocab_items id=2 has two meanings: "to drink", "to swallow"
            create_card_via_api(client, content_id=2, content_table="vocab_items", card_type="vocab_meaning")
            r = client.get("/api/srs/due")
        card = r.json()["data"][0]
        assert card["display_prompt"] == "飲む"
        assert "to drink" in card["display_answer"]

    def test_unknown_content_table_display_fields_are_none(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            create_card_via_api(client, content_id=1, content_table="unknown_table")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["display_prompt"] is None
        assert data[0]["display_answer"] is None
        assert data[0]["display_formation"] is None
        assert data[0]["display_sentences"] is None
        assert data[0]["display_readings"] is None

    def test_missing_content_id_display_fields_are_none(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # content_id=999 does not exist in seeded content.db
            create_card_via_api(client, content_id=999, content_table="grammar_points")
            r = client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["display_prompt"] is None
        assert data[0]["display_answer"] is None
        assert data[0]["display_formation"] is None
        assert data[0]["display_sentences"] is None
