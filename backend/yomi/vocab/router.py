"""Vocab API routes."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from yomi.auth.dependencies import get_current_user
from yomi.deps import get_content_db
from yomi.users.repository import UserRecord
from yomi.vocab.repository import get_vocab_by_id, search_vocab

router = APIRouter(prefix="/api/vocab", tags=["vocab"])


@router.get("/search")
def vocab_search(
    q: Annotated[str, Query(min_length=1)],
    level: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    _user: UserRecord = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    try:
        items = search_vocab(conn, q, level=level, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return {"data": [i.model_dump() for i in items], "error": None}


@router.get("/{vocab_id}")
def vocab_detail(
    vocab_id: int,
    _user: UserRecord = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_content_db),
) -> dict[str, object]:
    item = get_vocab_by_id(conn, vocab_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocab item not found")
    return {"data": item.model_dump(), "error": None}
