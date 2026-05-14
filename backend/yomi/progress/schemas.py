"""Pydantic schemas for progress API responses."""

from __future__ import annotations

from pydantic import BaseModel


class CardsByState(BaseModel):
    new: int = 0
    learning: int = 0
    review: int = 0
    relearning: int = 0


class ProgressSummary(BaseModel):
    total_cards: int
    due_today: int
    cards_by_state: CardsByState
    total_reviews: int
    reviews_today: int
    current_streak: int


class HeatmapEntry(BaseModel):
    date: str
    reviews_done: int
    lessons_done: int
    minutes_est: int


class WeakPoint(BaseModel):
    card_type: str
    content_table: str
    total_reviews: int
    correct_rate: float
