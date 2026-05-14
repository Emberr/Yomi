"""SRS API routes — due cards, card creation, review submission."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from yomi.auth.csrf import require_csrf
from yomi.auth.dependencies import get_current_user
from yomi.db.sqlite import open_user_db
from yomi.srs.engine import apply_review, card_state_name, due_iso, reconstruct_card
from yomi.srs.repository import (
    create_card,
    get_card_by_id,
    get_due_cards,
    insert_review_history,
    update_card_after_review,
    upsert_daily_activity,
)
from yomi.srs.schemas import CreateCardRequest, ReviewResponse, SubmitReviewRequest
from yomi.users.repository import UserRecord

router = APIRouter(prefix="/api/srs", tags=["srs"])

_DEFAULT_DUE_LIMIT = 20


@router.get("/due")
def srs_due(
    request: Request,
    user: UserRecord = Depends(get_current_user),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        cards = get_due_cards(conn, user_id=user.id, limit=_DEFAULT_DUE_LIMIT)
    return {"data": [c.to_response().model_dump() for c in cards], "error": None}


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
