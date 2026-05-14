"""Shared FastAPI dependencies for content database access."""

from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import HTTPException, Request, status

from yomi.db.sqlite import open_content_db_readonly


def get_content_db(request: Request) -> Generator[sqlite3.Connection, None, None]:
    path = request.app.state.settings.content_db_path
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content database not initialized. Run ingestion first.",
        )
    try:
        conn = open_content_db_readonly(path)
    except sqlite3.OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content database unavailable.",
        )
    try:
        yield conn
    finally:
        conn.close()
