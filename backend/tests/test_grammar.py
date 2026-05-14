"""Tests for grammar API routes (M3.2)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.main import create_app
from yomi.users.repository import create_user

_REAL_CONTENT_DB = Path("/data/content.db")


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
    """Create minimal content.db with Phase 3 schema and fixture rows."""
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

            CREATE TABLE IF NOT EXISTS example_sentences (
                id INTEGER PRIMARY KEY,
                grammar_id INTEGER NOT NULL REFERENCES grammar_points(id),
                japanese TEXT NOT NULL,
                reading TEXT NOT NULL DEFAULT '',
                translation TEXT NOT NULL DEFAULT '',
                audio_url TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS grammar_fts
                USING fts5(title, short_desc, content='grammar_points', content_rowid='id');

            INSERT INTO grammar_points
                (slug, title, jlpt_level, jlpt_source, short_desc, long_desc,
                 formation_pattern, common_mistakes, tags, sort_order, source_file)
            VALUES
                ('te-kudasai', '〜てください', 'N5', 'hanabira', 'Politely request.',
                 'Used to make polite requests.', 'Verb て-form + ください', '',
                 '["request","te-form"]', 1, 'n5.json'),
                ('ga-arimasu', '〜があります', 'N5', 'hanabira', 'There is (inanimate).',
                 'Expresses existence of inanimate things.', 'Noun + があります', '',
                 '["existence"]', 2, 'n5.json'),
                ('node', '〜ので', 'N4', 'hanabira', 'Because / since.',
                 'Expresses reason or cause.', 'Clause + ので + Clause', '',
                 '["reason","conjunction"]', 1, 'n4.json');

            INSERT INTO grammar_fts (rowid, title, short_desc)
            SELECT id, title, short_desc FROM grammar_points;

            INSERT INTO example_sentences
                (grammar_id, japanese, reading, translation, audio_url, tags)
            VALUES
                (1, 'ここに座ってください。', 'ここにすわってください。', 'Please sit here.', '', '[]'),
                (1, '静かにしてください。', 'しずかにしてください。', 'Please be quiet.', '', '[]');
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


class TestGrammarList:
    def test_returns_all_grammar_points(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar")
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is None
        assert len(body["data"]) == 3

    def test_filters_by_level(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar?level=N5")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        assert all(item["jlpt_level"] == "N5" for item in data)

    def test_empty_result_for_unknown_level(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar?level=N1")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_summary_fields_present(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar?level=N5")
        item = r.json()["data"][0]
        assert {"id", "slug", "title", "jlpt_level", "short_desc"} <= item.keys()

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/grammar")
        assert r.status_code == 401

    def test_returns_503_when_content_db_missing(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        # Do NOT seed content db
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar")
        assert r.status_code == 503


class TestGrammarDetail:
    def test_returns_full_detail_for_known_slug(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/te-kudasai")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["slug"] == "te-kudasai"
        assert data["title"] == "〜てください"
        assert data["jlpt_level"] == "N5"
        assert isinstance(data["tags"], list)
        assert "request" in data["tags"]

    def test_returns_404_for_unknown_slug(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/nonexistent-slug")
        assert r.status_code == 404

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/grammar/te-kudasai")
        assert r.status_code == 401

    def test_detail_has_all_required_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/te-kudasai")
        data = r.json()["data"]
        expected = {
            "id", "slug", "title", "jlpt_level", "jlpt_source",
            "short_desc", "long_desc", "formation_pattern",
            "common_mistakes", "tags", "sort_order", "source_file",
        }
        assert expected <= data.keys()


class TestGrammarSentences:
    def test_returns_sentences_for_known_slug(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/te-kudasai/sentences")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 2
        assert data[0]["japanese"] == "ここに座ってください。"

    def test_returns_empty_list_for_grammar_without_sentences(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/ga-arimasu/sentences")
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_returns_404_for_unknown_slug(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/nonexistent/sentences")
        assert r.status_code == 404

    def test_requires_authentication(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            r = client.get("/api/grammar/te-kudasai/sentences")
        assert r.status_code == 401

    def test_sentence_has_required_fields(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/te-kudasai/sentences")
        sentence = r.json()["data"][0]
        assert {"id", "grammar_id", "japanese", "reading", "translation", "audio_url", "tags"} <= sentence.keys()


class TestContentDbReadOnly:
    def test_content_db_cannot_be_written_via_api(self, tmp_path):
        """Content DB opened read-only: any write attempt raises OperationalError."""
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db(settings.content_db_path)
        from yomi.db.sqlite import open_content_db_readonly
        with open_content_db_readonly(settings.content_db_path) as conn:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute(
                    "INSERT INTO grammar_points (slug, title, jlpt_level) VALUES (?, ?, ?)",
                    ("x", "x", "N5"),
                )


def seed_content_db_with_nulls(path) -> None:
    """Seed content DB with NULL optional fields matching real Hanabira ingestion."""
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
                jlpt_level TEXT,
                jlpt_source TEXT,
                short_desc TEXT,
                long_desc TEXT,
                formation_pattern TEXT,
                common_mistakes TEXT,
                tags TEXT,
                sort_order INTEGER,
                source_file TEXT
            );

            CREATE TABLE IF NOT EXISTS example_sentences (
                id INTEGER PRIMARY KEY,
                grammar_id INTEGER NOT NULL REFERENCES grammar_points(id),
                japanese TEXT NOT NULL,
                reading TEXT,
                translation TEXT,
                audio_url TEXT,
                tags TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS grammar_fts
                USING fts5(title, short_desc, content='grammar_points', content_rowid='id');
        """)
        # Insert row matching real Hanabira data: common_mistakes=NULL, tags=NULL
        conn.execute(
            """INSERT INTO grammar_points
               (slug, title, jlpt_level, jlpt_source, short_desc, long_desc,
                formation_pattern, common_mistakes, tags, sort_order, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "uga-uga",
                "A うが B うが (A uga B uga)",
                "N1",
                "hanabira",
                "Expresses 'no matter how... or'.",
                "Full explanation text.",
                "Verb-volitional + うが",
                None,    # common_mistakes intentionally NULL (Hanabira doesn't supply this)
                None,    # tags intentionally NULL
                0,
                "hanabira:n1.json",
            ),
        )
        grammar_id = conn.execute(
            "SELECT id FROM grammar_points WHERE slug='uga-uga'"
        ).fetchone()[0]
        # Insert sentences with NULL audio_url and NULL tags (matching real data)
        conn.execute(
            """INSERT INTO example_sentences
               (grammar_id, japanese, reading, translation, audio_url, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (grammar_id, "何が起きようが諦めない。", "Nani ga okiyou ga akiramenai.", "No matter what.", None, None),
        )
        conn.execute("INSERT INTO grammar_fts (rowid, title, short_desc) SELECT id, title, short_desc FROM grammar_points")
        conn.commit()


class TestNullableFieldsNoServerError:
    """Regression tests: NULL common_mistakes / audio_url must not cause 500."""

    def test_grammar_detail_null_common_mistakes_returns_200(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db_with_nulls(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/uga-uga")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["common_mistakes"] is None
        assert data["tags"] == []

    def test_grammar_sentences_null_audio_url_returns_200(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db_with_nulls(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar/uga-uga/sentences")
        assert r.status_code == 200
        sentences = r.json()["data"]
        assert len(sentences) == 1
        assert sentences[0]["audio_url"] is None
        assert sentences[0]["tags"] == []

    def test_grammar_list_null_fields_returns_200(self, tmp_path):
        settings = make_settings(tmp_path)
        seed_user(settings)
        seed_content_db_with_nulls(settings.content_db_path)
        app = create_app(settings)
        with TestClient(app) as client:
            login(client)
            r = client.get("/api/grammar")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1


@pytest.mark.skipif(
    not _REAL_CONTENT_DB.exists(),
    reason="Real content.db not available — run ingestion first",
)
class TestRealContentDbAllSlugs:
    """Smoke-test every grammar slug in the real content.db directly via repository."""

    def test_all_slugs_detail_no_exception(self):
        from yomi.db.sqlite import open_content_db_readonly
        from yomi.grammar.repository import get_grammar_by_slug, list_grammar

        conn = open_content_db_readonly(_REAL_CONTENT_DB)
        try:
            all_items = list_grammar(conn)
            assert len(all_items) > 50, "Expected ≥50 grammar points from real ingestion"
            errors: list[str] = []
            for item in all_items:
                try:
                    detail = get_grammar_by_slug(conn, item.slug)
                    assert detail is not None, f"get_grammar_by_slug returned None for {item.slug!r}"
                except Exception as exc:
                    errors.append(f"{item.slug}: {exc}")
            assert errors == [], "Errors on detail fetch:\n" + "\n".join(errors)
        finally:
            conn.close()

    def test_all_slugs_sentences_no_exception(self):
        from yomi.db.sqlite import open_content_db_readonly
        from yomi.grammar.repository import list_grammar, list_grammar_sentences

        conn = open_content_db_readonly(_REAL_CONTENT_DB)
        try:
            all_items = list_grammar(conn)
            errors: list[str] = []
            for item in all_items:
                try:
                    list_grammar_sentences(conn, item.id)
                except Exception as exc:
                    errors.append(f"{item.slug}: {exc}")
            assert errors == [], "Errors on sentences fetch:\n" + "\n".join(errors)
        finally:
            conn.close()
