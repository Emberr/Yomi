"""Tests for vocab API routes (M3.2)."""

from __future__ import annotations

import json
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


def seed_content_db(path) -> None:
    """Create minimal content.db with vocab tables and fixture rows."""
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO content_metadata (key, value) VALUES ('schema_version', '2');

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

            INSERT INTO vocab_items
                (jmdict_id, slug, jlpt_level, jlpt_source,
                 kanji_forms, reading_forms, meanings, pos_tags, frequency)
            VALUES
                ('1000040', 'taberu-1000040', 'N5', 'jmdict',
                 '["食べる"]', '["たべる"]', '["to eat"]', '["v1"]', 9800),
                ('1000050', 'nomu-1000050', 'N5', 'jmdict',
                 '["飲む"]', '["のむ"]', '["to drink","to swallow"]', '["v5m"]', 9500),
                ('1002980', 'iku-1002980', 'N5', 'jmdict',
                 '["行く","往く"]', '["いく","ゆく"]', '["to go"]', '["v5k-s"]', 9900),
                ('2086640', 'benkyou-2086640', 'N4', 'jmdict',
                 '["勉強"]', '["べんきょう"]', '["study","diligence"]', '["n","vs"]', 8000),
                ('1001610', 'kuru-1001610', NULL, 'jmdict',
                 '["来る"]', '["くる"]', '["to come"]', '["vk"]', 9700);

            INSERT INTO vocab_fts (rowid, kanji_forms, reading_forms, meanings)
            SELECT id, kanji_forms, reading_forms, meanings FROM vocab_items;
        """)
        conn.commit()


def login(client: TestClient, username: str = "alice", password: str = "alicepass") -> None:
    r = client.get("/api/auth/csrf-token")
    csrf = r.json()["data"]["csrf_token"]
    client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-CSRF-Token": csrf},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVocabSearch:
    def test_search_returns_match(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=食べる")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 1
        slugs = [item["slug"] for item in data]
        assert "taberu-1000040" in slugs

    def test_search_by_reading(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=のむ")
        assert r.status_code == 200
        data = r.json()["data"]
        assert any(item["slug"] == "nomu-1000050" for item in data)

    def test_search_filters_by_level(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=study&level=N4")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 1
        assert all(item["jlpt_level"] == "N4" for item in data)

    def test_search_empty_result(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=zzznomatch")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_search_respects_limit(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=to&limit=2")
        assert r.status_code == 200
        assert len(r.json()["data"]) <= 2

    def test_search_summary_fields_present(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=食べる")
        item = r.json()["data"][0]
        assert {"id", "jmdict_id", "slug", "jlpt_level", "kanji_forms", "reading_forms", "meanings"} <= item.keys()
        assert isinstance(item["kanji_forms"], list)
        assert isinstance(item["reading_forms"], list)
        assert isinstance(item["meanings"], list)

    def test_malformed_fts_query_returns_422(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # FTS5 syntax error: unmatched quote
            r = client.get('/api/vocab/search?q="unclosed')
        assert r.status_code == 422

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/vocab/search?q=食べる")
        assert r.status_code == 401

    def test_returns_503_when_content_db_missing(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        # Do NOT seed content db
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=食べる")
        assert r.status_code == 503

    def test_missing_q_param_returns_422(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search")
        assert r.status_code == 422


class TestVocabDetail:
    def test_returns_detail_for_known_id(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # First get id from search
            r = client.get("/api/vocab/search?q=食べる")
            vocab_id = r.json()["data"][0]["id"]
            r2 = client.get(f"/api/vocab/{vocab_id}")
        assert r2.status_code == 200
        data = r2.json()["data"]
        assert data["jmdict_id"] == "1000040"
        assert data["slug"] == "taberu-1000040"
        assert "to eat" in data["meanings"]

    def test_returns_404_for_unknown_id(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/99999")
        assert r.status_code == 404

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/vocab/1")
        assert r.status_code == 401

    def test_detail_has_all_required_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/vocab/search?q=食べる")
            vocab_id = r.json()["data"][0]["id"]
            r2 = client.get(f"/api/vocab/{vocab_id}")
        data = r2.json()["data"]
        expected = {
            "id", "jmdict_id", "slug", "jlpt_level", "jlpt_source",
            "kanji_forms", "reading_forms", "meanings", "pos_tags", "frequency",
        }
        assert expected <= data.keys()
        assert isinstance(data["kanji_forms"], list)
        assert isinstance(data["pos_tags"], list)

    def test_jlpt_level_none_for_unlisted_word(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            # 来る has jlpt_level=NULL in our fixture
            r = client.get("/api/vocab/search?q=来る")
            data = r.json()["data"]
            assert len(data) >= 1
            vocab_id = next(d["id"] for d in data if d["slug"] == "kuru-1001610")
            r2 = client.get(f"/api/vocab/{vocab_id}")
        assert r2.json()["data"]["jlpt_level"] is None


class TestContentDbReadOnly:
    def test_vocab_items_table_cannot_be_written(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_content_db(settings.content_db_path)
        from yomi.db.sqlite import open_content_db_readonly
        with open_content_db_readonly(settings.content_db_path) as conn:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute(
                    "INSERT INTO vocab_items (jmdict_id, slug) VALUES (?, ?)",
                    ("9999999", "test-slug"),
                )
