"""Grammar API routes."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from yomi.auth.dependencies import get_current_user
from yomi.deps import get_content_db
from yomi.grammar.repository import get_grammar_by_slug, list_grammar, list_grammar_sentences
from yomi.grammar.schemas import ExampleSentence, GrammarDetail, GrammarSummary
from yomi.users.repository import UserRecord

router = APIRouter(prefix="/api/grammar", tags=["grammar"])


@router.get("")
def grammar_list(
    level: Annotated[str | None, Query()] = None,
    _user: UserRecord = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    items = list_grammar(conn, level=level)
    return {"data": [i.model_dump() for i in items], "error": None}


@router.get("/{slug}")
def grammar_detail(
    slug: str,
    _user: UserRecord = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    point = get_grammar_by_slug(conn, slug)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar point not found")
    return {"data": point.model_dump(), "error": None}


@router.get("/{slug}/sentences")
def grammar_sentences(
    slug: str,
    _user: UserRecord = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    point = get_grammar_by_slug(conn, slug)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar point not found")
    sentences = list_grammar_sentences(conn, point.id)
    return {"data": [s.model_dump() for s in sentences], "error": None}
