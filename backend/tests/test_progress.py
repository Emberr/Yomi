"""Tests for progress API routes (M3.6)."""

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
    """Minimal content.db so get_content_db dep doesn't 503."""
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO content_metadata (key, value)
            VALUES ('schema_version', '2');

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


def seed_card(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    state: str = "New",
    suspended: int = 0,
    due_offset_days: int = 0,
) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    due = (now + datetime.timedelta(days=due_offset_days)).isoformat()
    cur = conn.execute(
        "INSERT INTO srs_cards "
        "(user_id, card_type, content_id, content_table, state, due, created_at, suspended) "
        "VALUES (?, 'grammar_recognition', 1, 'grammar_points', ?, ?, ?, ?)",
        (user_id, state, due, now.isoformat(), suspended),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def seed_review(
    conn: sqlite3.Connection,
    *,
    card_id: int,
    user_id: int,
    rating: int = 3,
    days_ago: int = 0,
) -> None:
    reviewed_at = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    ).isoformat()
    conn.execute(
        "INSERT INTO review_history "
        "(card_id, user_id, rating, reviewed_at, state_before) "
        "VALUES (?, ?, ?, ?, 'New')",
        (card_id, user_id, rating, reviewed_at),
    )
    conn.commit()


def seed_daily_activity(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    date_iso: str,
    reviews_done: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO daily_activity (user_id, date, reviews_done) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, date) DO UPDATE SET reviews_done = ?",
        (user_id, date_iso, reviews_done, reviews_done),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Auth required tests
# ---------------------------------------------------------------------------


class TestProgressAuth:
    def test_summary_returns_401_when_unauthenticated(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/progress/summary")
        assert r.status_code == 401

    def test_heatmap_returns_401_when_unauthenticated(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/progress/heatmap")
        assert r.status_code == 401

    def test_weak_points_returns_401_when_unauthenticated(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/progress/weak-points")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# New user / empty state tests
# ---------------------------------------------------------------------------


class TestNewUserSummary:
    def test_new_user_summary_returns_zeros(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_cards"] == 0
        assert data["due_today"] == 0
        assert data["total_reviews"] == 0
        assert data["reviews_today"] == 0
        assert data["current_streak"] == 0
        assert data["cards_by_state"]["new"] == 0

    def test_new_user_heatmap_returns_empty_list(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/heatmap")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_new_user_weak_points_returns_empty_list(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/weak-points")
        assert r.status_code == 200
        assert r.json()["data"] == []


# ---------------------------------------------------------------------------
# Summary correctness tests
# ---------------------------------------------------------------------------


class TestSummaryCorrectness:
    def test_total_cards_counts_only_current_user(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings, username="alice", password="alicepass")
        bob = seed_user(settings, username="bob", password="bobpass")
        with open_user_db(settings.user_db_path) as conn:
            seed_card(conn, user_id=bob.id)
            seed_card(conn, user_id=bob.id)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["total_cards"] == 0

    def test_due_today_excludes_future_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            seed_card(conn, user_id=alice.id, due_offset_days=0)   # due now
            seed_card(conn, user_id=alice.id, due_offset_days=7)   # future
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["due_today"] == 1

    def test_due_today_excludes_suspended_cards(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            seed_card(conn, user_id=alice.id, due_offset_days=0, suspended=0)
            seed_card(conn, user_id=alice.id, due_offset_days=0, suspended=1)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["due_today"] == 1

    def test_reviews_today_correct_count(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            cid = seed_card(conn, user_id=alice.id)
            seed_review(conn, card_id=cid, user_id=alice.id, days_ago=0)
            seed_review(conn, card_id=cid, user_id=alice.id, days_ago=0)
            seed_review(conn, card_id=cid, user_id=alice.id, days_ago=2)  # not today
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["reviews_today"] == 2
        assert r.json()["data"]["total_reviews"] == 3

    def test_reviews_today_scoped_to_user(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings, username="alice", password="alicepass")
        bob = seed_user(settings, username="bob", password="bobpass")
        with open_user_db(settings.user_db_path) as conn:
            cid = seed_card(conn, user_id=bob.id)
            seed_review(conn, card_id=cid, user_id=bob.id, days_ago=0)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["reviews_today"] == 0
        assert r.json()["data"]["total_reviews"] == 0

    def test_cards_by_state_counts_correctly(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            seed_card(conn, user_id=alice.id, state="New")
            seed_card(conn, user_id=alice.id, state="New")
            seed_card(conn, user_id=alice.id, state="Review")
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        cbs = r.json()["data"]["cards_by_state"]
        assert cbs["new"] == 2
        assert cbs["review"] == 1
        assert cbs["learning"] == 0


# ---------------------------------------------------------------------------
# Streak tests
# ---------------------------------------------------------------------------


class TestStreak:
    def test_streak_zero_for_new_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["current_streak"] == 0

    def test_streak_counts_consecutive_days(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        today = datetime.date.today()
        with open_user_db(settings.user_db_path) as conn:
            for i in range(3):
                d = (today - datetime.timedelta(days=i)).isoformat()
                seed_daily_activity(conn, user_id=alice.id, date_iso=d)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["current_streak"] == 3

    def test_streak_grace_if_not_yet_reviewed_today(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        day_before = today - datetime.timedelta(days=2)
        with open_user_db(settings.user_db_path) as conn:
            seed_daily_activity(conn, user_id=alice.id, date_iso=yesterday.isoformat())
            seed_daily_activity(conn, user_id=alice.id, date_iso=day_before.isoformat())
            # No activity today — streak should still be 2 (grace)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["current_streak"] == 2

    def test_streak_broken_by_gap(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        today = datetime.date.today()
        # Activity today and 3 days ago — gap on days 1 and 2
        with open_user_db(settings.user_db_path) as conn:
            seed_daily_activity(conn, user_id=alice.id, date_iso=today.isoformat())
            seed_daily_activity(
                conn,
                user_id=alice.id,
                date_iso=(today - datetime.timedelta(days=3)).isoformat(),
            )
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/summary")
        assert r.json()["data"]["current_streak"] == 1


# ---------------------------------------------------------------------------
# Heatmap tests
# ---------------------------------------------------------------------------


class TestHeatmap:
    def test_heatmap_returns_current_user_only(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings, username="alice", password="alicepass")
        bob = seed_user(settings, username="bob", password="bobpass")
        with open_user_db(settings.user_db_path) as conn:
            seed_daily_activity(conn, user_id=bob.id, date_iso="2026-01-15", reviews_done=5)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            r = client.get("/api/progress/heatmap?year=2026")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_heatmap_year_filter_excludes_other_years(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            seed_daily_activity(conn, user_id=alice.id, date_iso="2025-06-01", reviews_done=3)
            seed_daily_activity(conn, user_id=alice.id, date_iso="2026-03-15", reviews_done=7)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/heatmap?year=2026")
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["date"] == "2026-03-15"
        assert data[0]["reviews_done"] == 7

    def test_heatmap_entry_has_required_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            seed_daily_activity(conn, user_id=alice.id, date_iso="2026-05-01", reviews_done=4)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/heatmap?year=2026")
        entry = r.json()["data"][0]
        assert "date" in entry
        assert "reviews_done" in entry
        assert "lessons_done" in entry
        assert "minutes_est" in entry


# ---------------------------------------------------------------------------
# Weak-points tests
# ---------------------------------------------------------------------------


class TestWeakPoints:
    def test_weak_points_returns_empty_for_new_user(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/weak-points")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_weak_points_scoped_to_user(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings, username="alice", password="alicepass")
        bob = seed_user(settings, username="bob", password="bobpass")
        with open_user_db(settings.user_db_path) as conn:
            cid = seed_card(conn, user_id=bob.id)
            # Bob has 6 reviews — enough to exceed min_reviews threshold
            for _ in range(6):
                seed_review(conn, card_id=cid, user_id=bob.id, rating=1)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client, "alice", "alicepass")
            r = client.get("/api/progress/weak-points")
        assert r.json()["data"] == []

    def test_weak_points_requires_min_reviews(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            cid = seed_card(conn, user_id=alice.id)
            # Only 3 reviews — below default min_reviews=5
            for _ in range(3):
                seed_review(conn, card_id=cid, user_id=alice.id, rating=1)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/weak-points")
        assert r.json()["data"] == []

    def test_weak_points_appears_with_enough_reviews(self, tmp_path):
        settings = make_settings(tmp_path)
        alice = seed_user(settings)
        with open_user_db(settings.user_db_path) as conn:
            cid = seed_card(conn, user_id=alice.id)
            for _ in range(6):
                seed_review(conn, card_id=cid, user_id=alice.id, rating=1)  # all Again
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/progress/weak-points")
        data = r.json()["data"]
        assert len(data) == 1
        assert data[0]["card_type"] == "grammar_recognition"
        assert data[0]["correct_rate"] == 0.0
