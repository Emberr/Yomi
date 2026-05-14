"""FSRS engine wiring — reconstruct Card from DB fields, apply review."""

from __future__ import annotations

import datetime

from fsrs import Card, Rating, ReviewLog, Scheduler, State

_SCHEDULER = Scheduler()

_STATE_NAME_TO_ENUM: dict[str, State] = {
    "Learning": State.Learning,
    "Review": State.Review,
    "Relearning": State.Relearning,
}


def _parse_dt(value: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def reconstruct_card(
    db_id: int,
    state: str,
    step: int | None,
    stability: float | None,
    difficulty: float | None,
    due: str,
    last_review: str | None,
) -> Card:
    if state == "New":
        return Card(card_id=db_id)
    fsrs_state = _STATE_NAME_TO_ENUM[state]
    return Card(
        card_id=db_id,
        state=fsrs_state,
        step=step,
        stability=stability,
        difficulty=difficulty,
        due=_parse_dt(due),
        last_review=_parse_dt(last_review) if last_review else None,
    )


def apply_review(card: Card, rating: int) -> tuple[Card, ReviewLog]:
    return _SCHEDULER.review_card(card, Rating(rating))


def card_state_name(card: Card) -> str:
    return card.state.name


def due_iso(card: Card) -> str:
    dt = card.due
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()
