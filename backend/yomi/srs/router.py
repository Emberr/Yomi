"""SRS API routes — due cards, card creation, review submission."""

from __future__ import annotations

import datetime
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from yomi.auth.csrf import require_csrf
from yomi.auth.dependencies import get_current_user
from yomi.db.sqlite import open_user_db
from yomi.deps import get_content_db
from yomi.srs.engine import apply_review, card_state_name, due_iso, reconstruct_card
from yomi.srs.repository import (
    SrsCardRow,
    create_card,
    get_card_by_id,
    get_due_cards,
    insert_review_history,
    update_card_after_review,
    upsert_daily_activity,
)
from yomi.srs.schemas import CardResponse, CreateCardRequest, ReviewResponse, SubmitReviewRequest
from yomi.users.repository import UserRecord

router = APIRouter(prefix="/api/srs", tags=["srs"])

_DEFAULT_DUE_LIMIT = 20


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _enrich_display(content_conn: sqlite3.Connection, card: SrsCardRow) -> dict[str, object]:
    if card.content_table == "grammar_points":
        row = content_conn.execute(
            "SELECT title, short_desc, formation_pattern FROM grammar_points WHERE id = ?",
            (card.content_id,),
        ).fetchone()
        if row is None:
            return {}
        title, short_desc, formation = row[0], row[1], row[2]
        sentence_rows = content_conn.execute(
            "SELECT japanese, reading, translation FROM example_sentences "
            "WHERE grammar_id = ? ORDER BY id LIMIT 3",
            (card.content_id,),
        ).fetchall()
        sentences = [
            {"japanese": sr[0], "reading": sr[1] or "", "translation": sr[2] or ""}
            for sr in sentence_rows
        ]
        return {
            "display_prompt": title,
            "display_answer": short_desc or None,
            "display_formation": formation if formation else None,
            "display_sentences": sentences if sentences else None,
        }
    elif card.content_table == "vocab_items":
        row = content_conn.execute(
            "SELECT kanji_forms, reading_forms, meanings FROM vocab_items WHERE id = ?",
            (card.content_id,),
        ).fetchone()
        if row is None:
            return {}
        kanji = _parse_json_list(row[0])
        readings = _parse_json_list(row[1])
        meanings = _parse_json_list(row[2])
        prompt = kanji[0] if kanji else (readings[0] if readings else None)
        answer = "、".join(meanings[:3]) if meanings else None
        return {
            "display_prompt": prompt,
            "display_answer": answer,
            "display_readings": readings if readings else None,
        }
    return {}


def _card_to_response(content_conn: sqlite3.Connection, card: SrsCardRow) -> CardResponse:
    enrichment = _enrich_display(content_conn, card)
    resp = card.to_response()
    resp.display_prompt = enrichment.get("display_prompt")  # type: ignore[assignment]
    resp.display_answer = enrichment.get("display_answer")  # type: ignore[assignment]
    resp.display_formation = enrichment.get("display_formation")  # type: ignore[assignment]
    resp.display_sentences = enrichment.get("display_sentences")  # type: ignore[assignment]
    resp.display_readings = enrichment.get("display_readings")  # type: ignore[assignment]
    return resp


@router.get("/due")
def srs_due(
    request: Request,
    user: UserRecord = Depends(get_current_user),
    content_conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        cards = get_due_cards(conn, user_id=user.id, limit=_DEFAULT_DUE_LIMIT)
    return {"data": [_card_to_response(content_conn, c).model_dump() for c in cards], "error": None}


@router.post("/cards")
def srs_create_card(
    payload: CreateCardRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        card = create_card(
            conn,
            user_id=user.id,
            card_type=payload.card_type,
            content_id=payload.content_id,
            content_table=payload.content_table,
        )
        conn.commit()
    return {"data": card.to_response().model_dump(), "error": None}


@router.post("/review")
def srs_review(
    payload: SubmitReviewRequest,
    request: Request,
    user: UserRecord = Depends(get_current_user),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        card = get_card_by_id(conn, payload.card_id)
        if card is None or card.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )

        fsrs_card = reconstruct_card(
            db_id=card.id,
            state=card.state,
            step=card.step,
            stability=card.stability,
            difficulty=card.difficulty,
            due=card.due,
            last_review=card.last_review,
        )

        state_before = card.state
        stability_before = card.stability
        difficulty_before = card.difficulty

        new_fsrs_card, _review_log = apply_review(fsrs_card, payload.rating)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        today = datetime.date.today().isoformat()
        new_state = card_state_name(new_fsrs_card)
        new_due = due_iso(new_fsrs_card)

        update_card_after_review(
            conn,
            card_id=card.id,
            state=new_state,
            stability=new_fsrs_card.stability,
            difficulty=new_fsrs_card.difficulty,
            step=new_fsrs_card.step,
            due=new_due,
            last_review=now,
        )

        insert_review_history(
            conn,
            card_id=card.id,
            user_id=user.id,
            rating=payload.rating,
            user_answer=payload.user_answer,
            ai_score=payload.ai_score,
            ai_feedback=payload.ai_feedback,
            ai_overridden=payload.ai_overridden,
            time_taken_ms=payload.time_taken_ms,
            state_before=state_before,
            stability_before=stability_before,
            difficulty_before=difficulty_before,
            reviewed_at=now,
        )

        upsert_daily_activity(conn, user_id=user.id, date=today)

        conn.commit()

    return {
        "data": ReviewResponse(
            card_id=card.id,
            state=new_state,
            due=new_due,
            stability=new_fsrs_card.stability,
            difficulty=new_fsrs_card.difficulty,
        ).model_dump(),
        "error": None,
    }
