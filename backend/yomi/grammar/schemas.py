"""Pydantic schemas for grammar API responses."""

from __future__ import annotations

from pydantic import BaseModel


class GrammarSummary(BaseModel):
    id: int
    slug: str
    title: str
    jlpt_level: str
    short_desc: str


class GrammarDetail(BaseModel):
    id: int
    slug: str
    title: str
    jlpt_level: str
    jlpt_source: str
    short_desc: str
    long_desc: str
    formation_pattern: str
    common_mistakes: str
    tags: list[str]
    sort_order: int
    source_file: str


class ExampleSentence(BaseModel):
    id: int
    grammar_id: int
    japanese: str
    reading: str
    translation: str
    audio_url: str
    tags: list[str]
