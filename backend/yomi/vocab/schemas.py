"""Pydantic schemas for vocab API responses."""

from __future__ import annotations

from pydantic import BaseModel


class VocabSummary(BaseModel):
    id: int
    jmdict_id: str
    slug: str
    jlpt_level: str | None
    kanji_forms: list[str]
    reading_forms: list[str]
    meanings: list[str]


class VocabDetail(BaseModel):
    id: int
    jmdict_id: str
    slug: str
    jlpt_level: str | None
    jlpt_source: str | None
    kanji_forms: list[str]
    reading_forms: list[str]
    meanings: list[str]
    pos_tags: list[str]
    frequency: int | None
