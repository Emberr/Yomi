"""Phase 3 content database ingestion for Yomi.

Populates content.db with grammar points (Hanabira) and vocabulary
(JMDict simplified). Downloads source files to a local cache directory
and never touches user.db.

Sources:
  - Hanabira Japanese Content (CC license, attribution to hanabira.org)
    https://github.com/tristcoil/hanabira.org-japanese-content
  - JMDict simplified by scriptin (EDRDG license)
    https://github.com/scriptin/jmdict-simplified

bunpou/japanese-grammar-db is deferred: confirmed GPL-3.0 license creates
legal ambiguity when combined with AGPL-3.0 code distribution. Excluded
until legal review confirms compatibility.

Environment variables:
  DB_CONTENT_PATH   path to content.db   (default /data/content.db)
  SOURCES_DIR       download cache dir   (default /data/sources)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import ijson
import requests

CONTENT_SCHEMA_VERSION = "2"

# ---------------------------------------------------------------------------
# Source URLs — pinned to a known-good release.
# To update JMDict: change the version tag in JMDICT_DOWNLOAD_URL and bump
# JMDICT_VERSION. Re-run ingestion to refresh /data/sources.
# ---------------------------------------------------------------------------

HANABIRA_BASE_URL = (
    "https://raw.githubusercontent.com"
    "/tristcoil/hanabira.org-japanese-content/main/grammar_json"
)
HANABIRA_LEVELS = ["N5", "N4", "N3", "N2", "N1"]
HANABIRA_FILENAME_TMPL = "grammar_ja_{level}_full_alphabetical_0001.json"

JMDICT_VERSION = "3.6.2+20260511143416"
JMDICT_VERSION_ENCODED = "3.6.2%2B20260511143416"
JMDICT_DOWNLOAD_URL = (
    "https://github.com/scriptin/jmdict-simplified/releases/download"
    f"/{JMDICT_VERSION_ENCODED}"
    f"/jmdict-eng-{JMDICT_VERSION_ENCODED}.json.zip"
)
JMDICT_ZIP_FILENAME = "jmdict-eng.json.zip"
JMDICT_JSON_FILENAME = "jmdict-eng.json"

DownloadFn = Callable[[str, Path], None]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestionSettings:
    content_db_path: Path
    sources_dir: Path

    @classmethod
    def from_env(cls) -> "IngestionSettings":
        return cls(
            content_db_path=Path(os.getenv("DB_CONTENT_PATH", "/data/content.db")),
            sources_dir=Path(os.getenv("SOURCES_DIR", "/data/sources")),
        )


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection) -> dict[str, object]:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-32000")
    journal_mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    conn.execute("PRAGMA synchronous=NORMAL")
    synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    cache_size = conn.execute("PRAGMA cache_size").fetchone()[0]
    return {
        "journal_mode": journal_mode,
        "synchronous": synchronous,
        "foreign_keys": foreign_keys,
        "cache_size": cache_size,
    }


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create all content tables, indexes, and FTS virtual tables."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS content_metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS grammar_points (
            id                INTEGER PRIMARY KEY,
            slug              TEXT UNIQUE NOT NULL,
            title             TEXT NOT NULL,
            jlpt_level        TEXT,
            jlpt_source       TEXT,
            short_desc        TEXT,
            long_desc         TEXT,
            formation_pattern TEXT,
            common_mistakes   TEXT,
            tags              TEXT,
            sort_order        INTEGER,
            source_file       TEXT
        );

        CREATE TABLE IF NOT EXISTS example_sentences (
            id         INTEGER PRIMARY KEY,
            grammar_id INTEGER NOT NULL
                           REFERENCES grammar_points(id) ON DELETE CASCADE,
            japanese   TEXT NOT NULL,
            reading    TEXT,
            translation TEXT,
            audio_url  TEXT,
            tags       TEXT
        );

        CREATE TABLE IF NOT EXISTS vocab_items (
            id            INTEGER PRIMARY KEY,
            jmdict_id     TEXT UNIQUE,
            slug          TEXT UNIQUE NOT NULL,
            jlpt_level    TEXT,
            jlpt_source   TEXT,
            kanji_forms   TEXT,
            reading_forms TEXT,
            meanings      TEXT,
            pos_tags      TEXT,
            frequency     INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_grammar_jlpt
            ON grammar_points(jlpt_level);
        CREATE INDEX IF NOT EXISTS idx_vocab_jlpt_freq
            ON vocab_items(jlpt_level, frequency);
        CREATE INDEX IF NOT EXISTS idx_sentences_grammar
            ON example_sentences(grammar_id);
        """
    )

    existing = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "grammar_fts" not in existing:
        conn.execute(
            """
            CREATE VIRTUAL TABLE grammar_fts USING fts5(
                title,
                short_desc,
                content='grammar_points',
                content_rowid='id'
            )
            """
        )
    if "vocab_fts" not in existing:
        conn.execute(
            """
            CREATE VIRTUAL TABLE vocab_fts USING fts5(
                kanji_forms,
                reading_forms,
                meanings,
                content='vocab_items',
                content_rowid='id'
            )
            """
        )


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild FTS indexes from content tables."""
    conn.execute("INSERT INTO grammar_fts(grammar_fts) VALUES('rebuild')")
    conn.execute("INSERT INTO vocab_fts(vocab_fts) VALUES('rebuild')")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def download_file(url: str, dest: Path) -> None:
    """Download url to dest, skip if dest already exists."""
    if dest.exists():
        print(f"  cached: {dest.name}")
        return
    _ensure_dir(dest.parent)
    print(f"  downloading {dest.name} ...")
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)
    print(f"  saved {dest.name} ({dest.stat().st_size:,} bytes)")


def _extract_zip_json(zip_path: Path, dest_dir: Path) -> Path:
    """Extract the first JSON file from zip_path into dest_dir/jmdict-eng.json."""
    target = dest_dir / JMDICT_JSON_FILENAME
    if target.exists():
        print(f"  cached: {JMDICT_JSON_FILENAME}")
        return target
    with zipfile.ZipFile(zip_path) as zf:
        json_names = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_names:
            raise RuntimeError(f"No JSON entry found in {zip_path}")
        source_name = json_names[0]
        print(f"  extracting {source_name} -> {JMDICT_JSON_FILENAME} ...")
        with zf.open(source_name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
    print(f"  extracted {JMDICT_JSON_FILENAME} ({target.stat().st_size:,} bytes)")
    return target


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------


def _make_grammar_slug(title: str, level: str, seen: set[str]) -> str:
    """Derive a URL-safe slug from a grammar title and JLPT level.

    Attempts to extract the romaji portion from parentheses, e.g.:
      "A が いちばん～ (A ga ichiban～)" -> "n5-a-ga-ichiban"
    Falls back to a hash when no ASCII characters survive normalization.
    """
    m = re.search(r"\(([^)]+)\)", title)
    base = m.group(1) if m else title
    base = re.sub(r"[~～〜]", "", base)
    base = unicodedata.normalize("NFKD", base)
    base = base.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"\s+", "-", base.strip())
    base = re.sub(r"-+", "-", base).strip("-").lower()
    base = base[:60]

    prefix = level.lower()
    slug = f"{prefix}-{base}" if base else f"{prefix}-{abs(hash(title)) % 0xFFFFFF:06x}"

    candidate = slug
    n = 2
    while candidate in seen:
        candidate = f"{slug}-{n}"
        n += 1
    seen.add(candidate)
    return candidate


# ---------------------------------------------------------------------------
# Grammar ingestion
# ---------------------------------------------------------------------------


def _ingest_grammar_file(
    conn: sqlite3.Connection,
    json_path: Path,
    level: str,
    seen_slugs: set[str],
) -> tuple[int, int]:
    """Ingest one Hanabira grammar level file. Returns (grammar_count, sentence_count)."""
    with open(json_path, encoding="utf-8") as fh:
        entries = json.load(fh)

    if not isinstance(entries, list):
        raise ValueError(f"Expected JSON array in {json_path}, got {type(entries)}")

    grammar_count = 0
    sentence_count = 0
    filename = json_path.name

    for sort_order, entry in enumerate(entries):
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        slug = _make_grammar_slug(title, level, seen_slugs)
        short_desc = (entry.get("short_explanation") or entry.get("short_desc") or "").strip()
        long_desc = (entry.get("long_explanation") or entry.get("long_desc") or "").strip()
        formation = (entry.get("formation") or entry.get("formation_pattern") or "").strip()

        conn.execute(
            """
            INSERT INTO grammar_points
                (slug, title, jlpt_level, jlpt_source, short_desc, long_desc,
                 formation_pattern, common_mistakes, tags, sort_order, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                title,
                level,
                "hanabira",
                short_desc,
                long_desc,
                formation,
                None,
                None,
                sort_order,
                f"hanabira:{filename}",
            ),
        )
        grammar_id = conn.execute(
            "SELECT id FROM grammar_points WHERE slug = ?", (slug,)
        ).fetchone()[0]

        for example in entry.get("examples", []):
            jp = (example.get("jp") or "").strip()
            if not jp:
                continue
            conn.execute(
                """
                INSERT INTO example_sentences
                    (grammar_id, japanese, reading, translation, audio_url, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    grammar_id,
                    jp,
                    (example.get("romaji") or "").strip(),
                    (example.get("en") or "").strip(),
                    None,
                    None,
                ),
            )
            sentence_count += 1

        grammar_count += 1

    return grammar_count, sentence_count


def ingest_hanabira_grammar(
    conn: sqlite3.Connection,
    sources_dir: Path,
    *,
    download_fn: DownloadFn = download_file,
) -> dict[str, int]:
    """Download and ingest Hanabira grammar JSON for all JLPT levels."""
    conn.execute("DELETE FROM grammar_points")

    seen_slugs: set[str] = set()
    total_grammar = 0
    total_sentences = 0

    for level in HANABIRA_LEVELS:
        filename = HANABIRA_FILENAME_TMPL.format(level=level)
        url = f"{HANABIRA_BASE_URL}/{filename}"
        dest = sources_dir / f"hanabira_{filename}"
        download_fn(url, dest)

        count_g, count_s = _ingest_grammar_file(conn, dest, level, seen_slugs)
        print(f"  {level}: {count_g} grammar points, {count_s} example sentences")
        total_grammar += count_g
        total_sentences += count_s

    return {"grammar_points": total_grammar, "example_sentences": total_sentences}


# ---------------------------------------------------------------------------
# Vocabulary ingestion
# ---------------------------------------------------------------------------


def _ingest_jmdict_file(
    conn: sqlite3.Connection,
    json_path: Path,
) -> int:
    """Ingest vocab from a JMDict simplified JSON file using streaming JSON parse.

    Uses ijson to avoid loading the full ~116MB JSON into memory at once.
    Returns entry count inserted.
    """
    print(f"  streaming {json_path.name} ...")
    total = 0
    commit_every = 500

    with open(json_path, "rb") as fh:
        for entry in ijson.items(fh, "words.item"):
            entry_id = entry.get("id", "")
            if not entry_id:
                continue

            kanji_list = [k["text"] for k in entry.get("kanji", [])]
            kana_list = [k["text"] for k in entry.get("kana", [])]

            meanings: list[str] = []
            pos_tags: list[str] = []
            for sense in entry.get("sense", []):
                for gloss in sense.get("gloss", []):
                    if gloss.get("lang") == "eng":
                        meanings.append(gloss["text"])
                if not pos_tags:
                    pos_tags = list(sense.get("partOfSpeech", []))

            frequency = sum(
                1 for k in entry.get("kanji", []) if k.get("common")
            ) + sum(1 for k in entry.get("kana", []) if k.get("common"))

            conn.execute(
                """
                INSERT INTO vocab_items
                    (jmdict_id, slug, jlpt_level, jlpt_source, kanji_forms,
                     reading_forms, meanings, pos_tags, frequency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(entry_id),
                    str(entry_id),
                    None,
                    None,
                    json.dumps(kanji_list, ensure_ascii=False),
                    json.dumps(kana_list, ensure_ascii=False),
                    json.dumps(meanings, ensure_ascii=False),
                    json.dumps(pos_tags, ensure_ascii=False),
                    frequency,
                ),
            )
            total += 1

            if total % commit_every == 0:
                conn.commit()
                if total % 25000 == 0:
                    print(f"  ... {total:,} entries")

    conn.commit()
    return total


def ingest_jmdict(
    conn: sqlite3.Connection,
    sources_dir: Path,
    *,
    download_fn: DownloadFn = download_file,
) -> dict[str, int]:
    """Download JMDict simplified zip and ingest vocabulary."""
    zip_dest = sources_dir / JMDICT_ZIP_FILENAME
    download_fn(JMDICT_DOWNLOAD_URL, zip_dest)
    json_path = _extract_zip_json(zip_dest, sources_dir)

    conn.execute("DELETE FROM vocab_items")
    count = _ingest_jmdict_file(conn, json_path)
    return {"vocab_items": count}


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def initialize_content_db(
    path: Path,
    sources_dir: Path | None = None,
    *,
    _download_fn: DownloadFn = download_file,
) -> dict[str, object]:
    """Initialize content.db at path with schema v2 and ingest all sources.

    Idempotent: existing content is replaced on re-run.
    Never opens or modifies user.db.
    """
    if sources_dir is None:
        sources_dir = path.parent / "sources"

    _ensure_dir(path.parent)
    _ensure_dir(sources_dir)

    conn = sqlite3.connect(path)
    try:
        pragmas = _apply_pragmas(conn)
        _create_schema(conn)
        conn.commit()

        print("Ingesting Hanabira grammar ...")
        grammar_stats = ingest_hanabira_grammar(
            conn, sources_dir, download_fn=_download_fn
        )
        conn.commit()

        print("Ingesting JMDict vocabulary ...")
        vocab_stats = ingest_jmdict(conn, sources_dir, download_fn=_download_fn)
        conn.commit()

        print("Rebuilding FTS indexes ...")
        _rebuild_fts(conn)

        conn.execute(
            """
            INSERT INTO content_metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (CONTENT_SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "path": str(path),
        "schema_version": CONTENT_SCHEMA_VERSION,
        "pragmas": pragmas,
        **grammar_stats,
        **vocab_stats,
    }


def main() -> None:
    settings = IngestionSettings.from_env()
    print(f"content DB : {settings.content_db_path}")
    print(f"sources dir: {settings.sources_dir}")
    result = initialize_content_db(settings.content_db_path, settings.sources_dir)
    print()
    print("Done.")
    print(f"  schema_version  : {result['schema_version']}")
    print(f"  grammar_points  : {result['grammar_points']}")
    print(f"  example_sentences: {result['example_sentences']}")
    print(f"  vocab_items     : {result['vocab_items']}")


if __name__ == "__main__":
    main()
