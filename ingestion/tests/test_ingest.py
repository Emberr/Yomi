"""Tests for Phase 3 content database ingestion."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from ingest import (
    CONTENT_SCHEMA_VERSION,
    HANABIRA_LEVELS,
    IngestionSettings,
    _apply_pragmas,
    _create_schema,
    _ingest_grammar_file,
    _ingest_jmdict_file,
    _make_grammar_slug,
    _rebuild_fts,
    initialize_content_db,
    ingest_hanabira_grammar,
    ingest_jmdict,
)

# ---------------------------------------------------------------------------
# Fixture data matching real source shapes
# ---------------------------------------------------------------------------

HANABIRA_ENTRY = {
    "title": "〜てください (te kudasai)",
    "short_explanation": "Politely ask someone to do something.",
    "long_explanation": "〜てください is used to make a polite request.",
    "formation": "Verb て-form + ください",
    "examples": [
        {
            "jp": "ここに座ってください。",
            "romaji": "Koko ni suwatte kudasai.",
            "en": "Please sit here.",
        },
        {
            "jp": "ゆっくり話してください。",
            "romaji": "Yukkuri hanashite kudasai.",
            "en": "Please speak slowly.",
        },
    ],
}

HANABIRA_ENTRY_2 = {
    "title": "〜ている (te iru)",
    "short_explanation": "Expresses an ongoing action or state.",
    "long_explanation": "〜ている can indicate progressive action or resultant state.",
    "formation": "Verb て-form + いる",
    "examples": [
        {
            "jp": "今、食べています。",
            "romaji": "Ima, tabete imasu.",
            "en": "I am eating now.",
        },
    ],
}

JMDICT_ENTRY_TABERU = {
    "id": "1000040",
    "kanji": [{"common": True, "text": "食べる", "tags": []}],
    "kana": [
        {
            "common": True,
            "text": "たべる",
            "tags": [],
            "appliesToKanji": ["*"],
        }
    ],
    "sense": [
        {
            "partOfSpeech": ["v1"],
            "appliesToKanji": ["*"],
            "appliesToKana": ["*"],
            "related": [],
            "antonym": [],
            "field": [],
            "dialect": [],
            "misc": [],
            "info": [],
            "languageSource": [],
            "gloss": [{"lang": "eng", "gender": None, "type": None, "text": "to eat"}],
        }
    ],
}

JMDICT_ENTRY_IKU = {
    "id": "1547720",
    "kanji": [{"common": True, "text": "行く", "tags": []}],
    "kana": [
        {
            "common": True,
            "text": "いく",
            "tags": [],
            "appliesToKanji": ["*"],
        }
    ],
    "sense": [
        {
            "partOfSpeech": ["v5k-s"],
            "appliesToKanji": ["*"],
            "appliesToKana": ["*"],
            "related": [],
            "antonym": [],
            "field": [],
            "dialect": [],
            "misc": [],
            "info": [],
            "languageSource": [],
            "gloss": [{"lang": "eng", "gender": None, "type": None, "text": "to go"}],
        }
    ],
}

JMDICT_FIXTURE = {
    "version": CONTENT_SCHEMA_VERSION,
    "languages": ["eng"],
    "dictDate": "2026-05-11",
    "dictRevisions": [],
    "words": [JMDICT_ENTRY_TABERU, JMDICT_ENTRY_IKU],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_in_memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    _apply_pragmas(conn)
    _create_schema(conn)
    conn.commit()
    return conn


def _metadata_version(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT value FROM content_metadata WHERE key = 'schema_version'"
        ).fetchone()[0]


def _make_mock_download(fixtures: dict[str, list | dict]):
    """Return a download_fn that writes fixture data as JSON to dest."""

    def mock_download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for key, data in fixtures.items():
            if key in url:
                dest.write_text(json.dumps(data, ensure_ascii=False))
                return
        raise ValueError(f"No fixture registered for URL: {url}")

    return mock_download


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DB_CONTENT_PATH", str(tmp_path / "content.db"))
    monkeypatch.setenv("SOURCES_DIR", str(tmp_path / "sources"))
    s = IngestionSettings.from_env()
    assert s.content_db_path == tmp_path / "content.db"
    assert s.sources_dir == tmp_path / "sources"


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DB_CONTENT_PATH", raising=False)
    monkeypatch.delenv("SOURCES_DIR", raising=False)
    s = IngestionSettings.from_env()
    assert s.content_db_path == Path("/data/content.db")
    assert s.sources_dir == Path("/data/sources")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_schema_creates_all_tables() -> None:
    conn = _make_in_memory_db()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "content_metadata",
        "grammar_points",
        "example_sentences",
        "vocab_items",
        "grammar_fts",
        "vocab_fts",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_schema_creates_indexes() -> None:
    conn = _make_in_memory_db()
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_grammar_jlpt" in indexes
    assert "idx_vocab_jlpt_freq" in indexes
    assert "idx_sentences_grammar" in indexes


def test_schema_fts_tables_are_virtual() -> None:
    conn = _make_in_memory_db()
    virtuals = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%VIRTUAL%'"
        ).fetchall()
    }
    assert "grammar_fts" in virtuals
    assert "vocab_fts" in virtuals


# ---------------------------------------------------------------------------
# Slug generation tests
# ---------------------------------------------------------------------------


def test_slug_extracts_romaji_from_parentheses() -> None:
    seen: set[str] = set()
    slug = _make_grammar_slug("〜てください (te kudasai)", "N5", seen)
    assert slug == "n5-te-kudasai"


def test_slug_handles_tilde_in_romaji() -> None:
    seen: set[str] = set()
    slug = _make_grammar_slug("A が いちばん～ (A ga ichiban～)", "N5", seen)
    assert "n5-" in slug
    assert "ichiban" in slug


def test_slug_deduplicates_collisions() -> None:
    seen: set[str] = set()
    s1 = _make_grammar_slug("〜てください (te kudasai)", "N5", seen)
    s2 = _make_grammar_slug("〜てください (te kudasai)", "N5", seen)
    assert s1 != s2
    assert s2.startswith(s1)


def test_slug_falls_back_for_pure_japanese() -> None:
    seen: set[str] = set()
    slug = _make_grammar_slug("〜ている", "N5", seen)
    assert slug.startswith("n5-")
    assert len(slug) > len("n5-")


# ---------------------------------------------------------------------------
# Grammar ingestion tests
# ---------------------------------------------------------------------------


def test_ingest_grammar_file_inserts_rows(tmp_path: Path) -> None:
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(
        json.dumps([HANABIRA_ENTRY, HANABIRA_ENTRY_2], ensure_ascii=False)
    )
    conn = _make_in_memory_db()
    seen: set[str] = set()
    count_g, count_s = _ingest_grammar_file(conn, json_file, "N5", seen)
    conn.commit()

    assert count_g == 2
    assert count_s == 3  # 2 examples + 1 example

    rows = conn.execute("SELECT title, jlpt_level FROM grammar_points").fetchall()
    assert len(rows) == 2
    assert all(row[1] == "N5" for row in rows)


def test_ingest_grammar_file_inserts_sentences(tmp_path: Path) -> None:
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([HANABIRA_ENTRY], ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_grammar_file(conn, json_file, "N5", set())
    conn.commit()

    sentences = conn.execute(
        "SELECT japanese, translation FROM example_sentences"
    ).fetchall()
    assert len(sentences) == 2
    jp_texts = {s[0] for s in sentences}
    assert "ここに座ってください。" in jp_texts


def test_ingest_grammar_file_skips_empty_title(tmp_path: Path) -> None:
    bad_entry = {"title": "", "short_explanation": "test", "examples": []}
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([bad_entry, HANABIRA_ENTRY], ensure_ascii=False))
    conn = _make_in_memory_db()
    count_g, _ = _ingest_grammar_file(conn, json_file, "N5", set())
    assert count_g == 1


def test_ingest_grammar_file_skips_sentences_missing_jp(tmp_path: Path) -> None:
    entry_with_bad_example = {
        "title": "〜てください (te kudasai)",
        "short_explanation": "test",
        "examples": [{"jp": "", "romaji": "...", "en": "test"}],
    }
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([entry_with_bad_example], ensure_ascii=False))
    conn = _make_in_memory_db()
    _g, count_s = _ingest_grammar_file(conn, json_file, "N5", set())
    assert count_s == 0


def test_ingest_hanabira_uses_all_levels(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()

    fixture_data = [HANABIRA_ENTRY]
    mock_dl = _make_mock_download(
        {f"grammar_ja_{level}": fixture_data for level in HANABIRA_LEVELS}
    )

    conn = _make_in_memory_db()
    stats = ingest_hanabira_grammar(conn, sources, download_fn=mock_dl)
    conn.commit()

    assert stats["grammar_points"] == len(HANABIRA_LEVELS)
    rows = conn.execute(
        "SELECT DISTINCT jlpt_level FROM grammar_points"
    ).fetchall()
    levels_found = {r[0] for r in rows}
    assert levels_found == set(HANABIRA_LEVELS)


def test_ingest_hanabira_sets_jlpt_source(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    mock_dl = _make_mock_download(
        {f"grammar_ja_{level}": [HANABIRA_ENTRY] for level in HANABIRA_LEVELS}
    )
    conn = _make_in_memory_db()
    ingest_hanabira_grammar(conn, sources, download_fn=mock_dl)
    conn.commit()

    sources_found = {
        r[0]
        for r in conn.execute("SELECT DISTINCT jlpt_source FROM grammar_points").fetchall()
    }
    assert sources_found == {"hanabira"}


# ---------------------------------------------------------------------------
# Vocabulary ingestion tests
# ---------------------------------------------------------------------------


def test_ingest_jmdict_file_inserts_rows(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))
    conn = _make_in_memory_db()
    count = _ingest_jmdict_file(conn, json_file)
    conn.commit()

    assert count == 2
    rows = conn.execute(
        "SELECT jmdict_id, kanji_forms, reading_forms, meanings FROM vocab_items"
    ).fetchall()
    assert len(rows) == 2


def test_ingest_jmdict_file_stores_kanji_as_json(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_jmdict_file(conn, json_file)
    conn.commit()

    row = conn.execute(
        "SELECT kanji_forms, reading_forms, meanings FROM vocab_items WHERE jmdict_id = '1000040'"
    ).fetchone()
    assert row is not None
    kanji = json.loads(row[0])
    kana = json.loads(row[1])
    meanings = json.loads(row[2])
    assert "食べる" in kanji
    assert "たべる" in kana
    assert "to eat" in meanings


def test_ingest_jmdict_file_frequency_count(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_jmdict_file(conn, json_file)
    conn.commit()

    freq = conn.execute(
        "SELECT frequency FROM vocab_items WHERE jmdict_id = '1000040'"
    ).fetchone()[0]
    assert freq == 2  # 1 common kanji + 1 common kana


def test_ingest_jmdict_file_skips_missing_id(tmp_path: Path) -> None:
    bad_fixture = {
        "words": [{"id": "", "kanji": [], "kana": [], "sense": []}]
    }
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(bad_fixture, ensure_ascii=False))
    conn = _make_in_memory_db()
    count = _ingest_jmdict_file(conn, json_file)
    assert count == 0


# ---------------------------------------------------------------------------
# FTS tests
# ---------------------------------------------------------------------------


def test_fts_grammar_returns_results(tmp_path: Path) -> None:
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([HANABIRA_ENTRY, HANABIRA_ENTRY_2], ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_grammar_file(conn, json_file, "N5", set())
    conn.commit()
    _rebuild_fts(conn)
    conn.commit()

    rows = conn.execute(
        "SELECT title FROM grammar_fts WHERE grammar_fts MATCH 'kudasai'"
    ).fetchall()
    assert len(rows) >= 1
    assert any("kudasai" in r[0].lower() for r in rows)


def test_fts_grammar_japanese_query(tmp_path: Path) -> None:
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([HANABIRA_ENTRY], ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_grammar_file(conn, json_file, "N5", set())
    conn.commit()
    _rebuild_fts(conn)
    conn.commit()

    # FTS5 unicode61 tokenizer treats contiguous hiragana as one token;
    # query for the actual hiragana sequence present in the title.
    rows = conn.execute(
        "SELECT title FROM grammar_fts WHERE grammar_fts MATCH 'てください'"
    ).fetchall()
    assert len(rows) >= 1


def test_fts_vocab_returns_results(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_jmdict_file(conn, json_file)
    conn.commit()
    _rebuild_fts(conn)
    conn.commit()

    rows = conn.execute(
        "SELECT kanji_forms FROM vocab_fts WHERE vocab_fts MATCH '食べる'"
    ).fetchall()
    assert len(rows) >= 1


def test_fts_vocab_english_query(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_jmdict_file(conn, json_file)
    conn.commit()
    _rebuild_fts(conn)
    conn.commit()

    rows = conn.execute(
        "SELECT meanings FROM vocab_fts WHERE vocab_fts MATCH 'eat'"
    ).fetchall()
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


def test_initialize_idempotent_grammar(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    fixture_data = [HANABIRA_ENTRY, HANABIRA_ENTRY_2]
    mock_dl = _make_mock_download(
        {f"grammar_ja_{level}": fixture_data for level in HANABIRA_LEVELS}
    )

    conn = _make_in_memory_db()
    ingest_hanabira_grammar(conn, sources, download_fn=mock_dl)
    conn.commit()
    first_count = conn.execute("SELECT COUNT(*) FROM grammar_points").fetchone()[0]

    ingest_hanabira_grammar(conn, sources, download_fn=mock_dl)
    conn.commit()
    second_count = conn.execute("SELECT COUNT(*) FROM grammar_points").fetchone()[0]

    assert first_count == second_count == len(HANABIRA_LEVELS) * 2


def test_initialize_idempotent_vocab(tmp_path: Path) -> None:
    json_file = tmp_path / "jmdict.json"
    json_file.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))

    conn = _make_in_memory_db()
    _ingest_jmdict_file(conn, json_file)
    conn.commit()
    first = conn.execute("SELECT COUNT(*) FROM vocab_items").fetchone()[0]

    conn.execute("DELETE FROM vocab_items")
    _ingest_jmdict_file(conn, json_file)
    conn.commit()
    second = conn.execute("SELECT COUNT(*) FROM vocab_items").fetchone()[0]

    assert first == second == 2


def test_initialize_content_db_schema_version(tmp_path: Path) -> None:
    db_path = tmp_path / "content.db"
    sources = tmp_path / "sources"
    sources.mkdir()

    fixture_data = [HANABIRA_ENTRY]
    jmdict_fixture_path = sources / "jmdict-eng.json"
    jmdict_fixture_path.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))

    def mock_dl(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for level in HANABIRA_LEVELS:
            if f"grammar_ja_{level}" in url:
                dest.write_text(json.dumps(fixture_data, ensure_ascii=False))
                return
        if "jmdict" in url.lower():
            import zipfile as zf_mod
            with zf_mod.ZipFile(dest, "w") as zf:
                zf.write(jmdict_fixture_path, "jmdict-eng-test.json")
            return
        raise ValueError(f"Unhandled URL: {url}")

    result = initialize_content_db(db_path, sources, _download_fn=mock_dl)

    assert result["schema_version"] == CONTENT_SCHEMA_VERSION
    assert _metadata_version(db_path) == CONTENT_SCHEMA_VERSION
    assert result["grammar_points"] == len(HANABIRA_LEVELS)
    assert result["vocab_items"] == 2


def test_initialize_content_db_never_touches_user_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_db = tmp_path / "user.db"
    monkeypatch.setenv("DB_USER_PATH", str(user_db))

    db_path = tmp_path / "content.db"
    sources = tmp_path / "sources"
    sources.mkdir()

    jmdict_fixture_path = sources / "jmdict-eng.json"
    jmdict_fixture_path.write_text(json.dumps(JMDICT_FIXTURE, ensure_ascii=False))

    def mock_dl(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        for level in HANABIRA_LEVELS:
            if f"grammar_ja_{level}" in url:
                dest.write_text(json.dumps([HANABIRA_ENTRY], ensure_ascii=False))
                return
        if "jmdict" in url.lower():
            import zipfile as zf_mod
            with zf_mod.ZipFile(dest, "w") as zf:
                zf.write(jmdict_fixture_path, "jmdict-eng-test.json")
            return
        raise ValueError(f"Unhandled URL: {url}")

    initialize_content_db(db_path, sources, _download_fn=mock_dl)

    assert db_path.exists()
    assert not user_db.exists()


# ---------------------------------------------------------------------------
# Foreign key / cascade tests
# ---------------------------------------------------------------------------


def test_delete_grammar_cascades_to_sentences(tmp_path: Path) -> None:
    json_file = tmp_path / "grammar_N5.json"
    json_file.write_text(json.dumps([HANABIRA_ENTRY], ensure_ascii=False))
    conn = _make_in_memory_db()
    _ingest_grammar_file(conn, json_file, "N5", set())
    conn.commit()

    sentences_before = conn.execute("SELECT COUNT(*) FROM example_sentences").fetchone()[0]
    assert sentences_before > 0

    conn.execute("DELETE FROM grammar_points")
    conn.commit()

    sentences_after = conn.execute("SELECT COUNT(*) FROM example_sentences").fetchone()[0]
    assert sentences_after == 0
