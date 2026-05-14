"""Pydantic schemas for SRS API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateCardRequest(BaseModel):
    content_id: int
    content_table: str
    card_type: str


class SubmitReviewRequest(BaseModel):
    card_id: int
    rating: int = Field(..., ge=1, le=4)
    user_answer: str | None = None
    ai_score: float | None = None
    ai_feedback: str | None = None
    ai_overridden: bool = False
    time_taken_ms: int | None = None


class CardResponse(BaseModel):
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


class ReviewResponse(BaseModel):
    card_id: int
    state: str
    due: str
    stability: float | None
    difficulty: float | None
