"""Progress database queries against user.db."""

from __future__ import annotations

import datetime
import sqlite3

from yomi.progress.schemas import CardsByState, HeatmapEntry, ProgressSummary, WeakPoint

_STATE_MAP = {
    "New": "new",
    "Learning": "learning",
    "Review": "review",
    "Relearning": "relearning",
}


def _compute_streak(conn: sqlite3.Connection, user_id: int, today: datetime.date) -> int:
    rows = conn.execute(
        "SELECT date FROM daily_activity "
        "WHERE user_id = ? AND reviews_done > 0 "
        "ORDER BY date DESC",
        (user_id,),
    ).fetchall()
    dates = {row[0] for row in rows}
    streak = 0
    cursor = today
    # Grace: if haven't reviewed today yet, start checking from yesterday
    if cursor.isoformat() not in dates:
        cursor = cursor - datetime.timedelta(days=1)
    while cursor.isoformat() in dates:
        streak += 1
        cursor = cursor - datetime.timedelta(days=1)
    return streak


def get_progress_summary(
    conn: sqlite3.Connection,
    user_id: int,
) -> ProgressSummary:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    today = datetime.date.today()
    today_start = datetime.datetime(
        today.year, today.month, today.day, tzinfo=datetime.timezone.utc
    ).isoformat()

    total_cards: int = conn.execute(
        "SELECT COUNT(*) FROM srs_cards WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    due_today: int = conn.execute(
        "SELECT COUNT(*) FROM srs_cards "
        "WHERE user_id = ? AND suspended = 0 AND due <= ?",
        (user_id, now),
    ).fetchone()[0]

    state_rows = conn.execute(
        "SELECT state, COUNT(*) FROM srs_cards WHERE user_id = ? GROUP BY state",
        (user_id,),
    ).fetchall()
    state_counts: dict[str, int] = {}
    for state, count in state_rows:
        key = _STATE_MAP.get(state)
        if key:
            state_counts[key] = count
    cards_by_state = CardsByState(**state_counts)

    total_reviews: int = conn.execute(
        "SELECT COUNT(*) FROM review_history WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    reviews_today: int = conn.execute(
        "SELECT COUNT(*) FROM review_history "
        "WHERE user_id = ? AND reviewed_at >= ?",
        (user_id, today_start),
    ).fetchone()[0]

    streak = _compute_streak(conn, user_id, today)

    return ProgressSummary(
        total_cards=total_cards,
        due_today=due_today,
        cards_by_state=cards_by_state,
        total_reviews=total_reviews,
        reviews_today=reviews_today,
        current_streak=streak,
    )


def get_heatmap(
    conn: sqlite3.Connection,
    user_id: int,
    year: int,
) -> list[HeatmapEntry]:
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    rows = conn.execute(
        "SELECT date, reviews_done, lessons_done, minutes_est "
        "FROM daily_activity "
        "WHERE user_id = ? AND date BETWEEN ? AND ? "
        "ORDER BY date",
        (user_id, year_start, year_end),
    ).fetchall()
    return [
        HeatmapEntry(
            date=row[0],
            reviews_done=row[1],
            lessons_done=row[2],
            minutes_est=row[3],
        )
        for row in rows
    ]


def get_weak_points(
    conn: sqlite3.Connection,
    user_id: int,
    min_reviews: int = 5,
) -> list[WeakPoint]:
    rows = conn.execute(
        "SELECT c.card_type, c.content_table, "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN r.rating >= 3 THEN 1 ELSE 0 END) AS correct "
        "FROM review_history r "
        "JOIN srs_cards c ON c.id = r.card_id "
        "WHERE r.user_id = ? "
        "GROUP BY c.card_type, c.content_table "
        "HAVING COUNT(*) >= ? "
        "ORDER BY (SUM(CASE WHEN r.rating >= 3 THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) ASC",
        (user_id, min_reviews),
    ).fetchall()
    return [
        WeakPoint(
            card_type=row[0],
            content_table=row[1],
            total_reviews=row[2],
            correct_rate=round(row[3] / row[2], 3) if row[2] > 0 else 0.0,
        )
        for row in rows
    ]
