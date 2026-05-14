"""Grammar database queries against content.db."""

from __future__ import annotations

import json
import sqlite3

from yomi.grammar.schemas import ExampleSentence, GrammarDetail, GrammarSummary


def list_grammar(
    conn: sqlite3.Connection,
    *,
    level: str | None = None,
) -> list[GrammarSummary]:
    if level is not None:
        rows = conn.execute(
            "SELECT id, slug, title, jlpt_level, short_desc "
            "FROM grammar_points WHERE jlpt_level = ? ORDER BY sort_order, id",
            (level,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, slug, title, jlpt_level, short_desc "
            "FROM grammar_points ORDER BY jlpt_level, sort_order, id"
        ).fetchall()
    return [
        GrammarSummary(id=r[0], slug=r[1], title=r[2], jlpt_level=r[3], short_desc=r[4])
        for r in rows
    ]


def get_grammar_by_slug(conn: sqlite3.Connection, slug: str) -> GrammarDetail | None:
    row = conn.execute(
        "SELECT id, slug, title, jlpt_level, jlpt_source, short_desc, long_desc, "
        "formation_pattern, common_mistakes, tags, sort_order, source_file "
        "FROM grammar_points WHERE slug = ?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return GrammarDetail(
        id=row[0],
        slug=row[1],
        title=row[2],
        jlpt_level=row[3],
        jlpt_source=row[4],
        short_desc=row[5],
        long_desc=row[6],
        formation_pattern=row[7],
        common_mistakes=row[8],
        tags=json.loads(row[9]) if row[9] else [],
        sort_order=row[10],
        source_file=row[11],
    )


def list_grammar_sentences(
    conn: sqlite3.Connection, grammar_id: int
) -> list[ExampleSentence]:
    rows = conn.execute(
        "SELECT id, grammar_id, japanese, reading, translation, audio_url, tags "
        "FROM example_sentences WHERE grammar_id = ? ORDER BY id",
        (grammar_id,),
    ).fetchall()
    return [
        ExampleSentence(
            id=r[0],
            grammar_id=r[1],
            japanese=r[2],
            reading=r[3],
            translation=r[4],
            audio_url=r[5],
            tags=json.loads(r[6]) if r[6] else [],
        )
        for r in rows
    ]
