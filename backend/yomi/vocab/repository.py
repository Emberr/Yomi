"""Vocab database queries against content.db."""

from __future__ import annotations

import json
import sqlite3

from yomi.vocab.schemas import VocabDetail, VocabSummary


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _row_to_summary(row: tuple) -> VocabSummary:
    return VocabSummary(
        id=row[0],
        jmdict_id=row[1],
        slug=row[2],
        jlpt_level=row[3] or None,
        kanji_forms=_parse_json_list(row[4]),
        reading_forms=_parse_json_list(row[5]),
        meanings=_parse_json_list(row[6]),
    )


def _row_to_detail(row: tuple) -> VocabDetail:
    return VocabDetail(
        id=row[0],
        jmdict_id=row[1],
        slug=row[2],
        jlpt_level=row[3] or None,
        jlpt_source=row[4],
        kanji_forms=_parse_json_list(row[5]),
        reading_forms=_parse_json_list(row[6]),
        meanings=_parse_json_list(row[7]),
        pos_tags=_parse_json_list(row[8]),
        frequency=row[9],
    )


def search_vocab(
    conn: sqlite3.Connection,
    q: str,
    *,
    level: str | None = None,
    limit: int = 20,
) -> list[VocabSummary]:
    limit = max(1, min(limit, 100))
    try:
        if level is not None:
            rows = conn.execute(
                "SELECT v.id, v.jmdict_id, v.slug, v.jlpt_level, "
                "v.kanji_forms, v.reading_forms, v.meanings "
                "FROM vocab_items v "
                "JOIN vocab_fts f ON f.rowid = v.id "
                "WHERE vocab_fts MATCH ? AND v.jlpt_level = ? "
                "ORDER BY v.frequency DESC NULLS LAST "
                "LIMIT ?",
                (q, level, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT v.id, v.jmdict_id, v.slug, v.jlpt_level, "
                "v.kanji_forms, v.reading_forms, v.meanings "
                "FROM vocab_items v "
                "JOIN vocab_fts f ON f.rowid = v.id "
                "WHERE vocab_fts MATCH ? "
                "ORDER BY v.frequency DESC NULLS LAST "
                "LIMIT ?",
                (q, limit),
            ).fetchall()
    except sqlite3.OperationalError as exc:
        raise ValueError(f"Invalid search query: {exc}") from exc
    return [_row_to_summary(r) for r in rows]


def get_vocab_by_id(conn: sqlite3.Connection, vocab_id: int) -> VocabDetail | None:
    row = conn.execute(
        "SELECT id, jmdict_id, slug, jlpt_level, jlpt_source, "
        "kanji_forms, reading_forms, meanings, pos_tags, frequency "
        "FROM vocab_items WHERE id = ?",
        (vocab_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_detail(row)
