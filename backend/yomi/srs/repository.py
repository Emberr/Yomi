"""SRS database queries against user.db."""

from __future__ import annotations

import datetime
import sqlite3
from dataclasses import dataclass

from yomi.srs.schemas import CardResponse


@dataclass
class SrsCardRow:
    id: int
    user_id: int
    card_type: str
    content_id: int
    content_table: str
    state: str
    difficulty: float | None
    stability: float | None
    step: int | None
    last_review: str | None
    due: str
    created_at: str
    suspended: bool

    def to_response(self) -> CardResponse:
        return CardResponse(
            id=self.id,
            user_id=self.user_id,
            card_type=self.card_type,
            content_id=self.content_id,
            content_table=self.content_table,
            state=self.state,
            difficulty=self.difficulty,
            stability=self.stability,
            step=self.step,
            last_review=self.last_review,
            due=self.due,
            created_at=self.created_at,
            suspended=bool(self.suspended),
        )


def _row_to_card(row: tuple) -> SrsCardRow:
    return SrsCardRow(
        id=row[0],
        user_id=row[1],
        card_type=row[2],
        content_id=row[3],
        content_table=row[4],
        state=row[5],
        difficulty=row[6],
        stability=row[7],
        step=row[8],
        last_review=row[9],
        due=row[10],
        created_at=row[11],
        suspended=bool(row[12]),
    )


_CARD_SELECT = (
    "SELECT id, user_id, card_type, content_id, content_table, "
    "state, difficulty, stability, step, last_review, due, created_at, suspended "
    "FROM srs_cards"
)


def create_card(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    card_type: str,
    content_id: int,
    content_table: str,
) -> SrsCardRow:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO srs_cards "
        "(user_id, card_type, content_id, content_table, state, due, created_at) "
        "VALUES (?, ?, ?, ?, 'New', ?, ?)",
        (user_id, card_type, content_id, content_table, now, now),
    )
    card_id = cur.lastrowid
    row = conn.execute(
        f"{_CARD_SELECT} WHERE id = ?",
        (card_id,),
    ).fetchone()
    return _row_to_card(row)


def get_card_by_id(conn: sqlite3.Connection, card_id: int) -> SrsCardRow | None:
    row = conn.execute(
        f"{_CARD_SELECT} WHERE id = ?",
        (card_id,),
    ).fetchone()
    return _row_to_card(row) if row else None


def get_due_cards(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    limit: int = 20,
) -> list[SrsCardRow]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = conn.execute(
        f"{_CARD_SELECT} "
        "WHERE user_id = ? AND suspended = 0 AND due <= ? "
        "ORDER BY due ASC LIMIT ?",
        (user_id, now, limit),
    ).fetchall()
    return [_row_to_card(r) for r in rows]


def update_card_after_review(
    conn: sqlite3.Connection,
    *,
    card_id: int,
    state: str,
    stability: float | None,
    difficulty: float | None,
    step: int | None,
    due: str,
    last_review: str,
) -> None:
    conn.execute(
        "UPDATE srs_cards SET state=?, stability=?, difficulty=?, step=?, due=?, last_review=? "
        "WHERE id=?",
        (state, stability, difficulty, step, due, last_review, card_id),
    )


def insert_review_history(
    conn: sqlite3.Connection,
    *,
    card_id: int,
    user_id: int,
    rating: int,
    user_answer: str | None,
    ai_score: float | None,
    ai_feedback: str | None,
    ai_overridden: bool,
    time_taken_ms: int | None,
    state_before: str,
    stability_before: float | None,
    difficulty_before: float | None,
    reviewed_at: str,
) -> None:
    conn.execute(
        "INSERT INTO review_history "
        "(card_id, user_id, rating, user_answer, ai_score, ai_feedback, "
        "ai_overridden, time_taken_ms, state_before, stability_before, "
        "difficulty_before, reviewed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            card_id, user_id, rating, user_answer, ai_score, ai_feedback,
            int(ai_overridden), time_taken_ms, state_before, stability_before,
            difficulty_before, reviewed_at,
        ),
    )


def upsert_daily_activity(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    date: str,
) -> None:
    conn.execute(
        """
        INSERT INTO daily_activity (user_id, date, reviews_done)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, date)
        DO UPDATE SET reviews_done = reviews_done + 1
        """,
        (user_id, date),
    )
