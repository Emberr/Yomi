"""Progress API routes — summary, heatmap, weak-points."""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from yomi.auth.dependencies import get_current_user
from yomi.db.sqlite import open_user_db
from yomi.progress.repository import get_heatmap, get_progress_summary, get_weak_points
from yomi.users.repository import UserRecord

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/summary")
def progress_summary(
    request: Request,
    user: UserRecord = Depends(get_current_user),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        summary = get_progress_summary(conn, user_id=user.id)
    return {"data": summary.model_dump(), "error": None}


@router.get("/heatmap")
def progress_heatmap(
    request: Request,
    year: Annotated[int, Query(ge=2000, le=2100)] = datetime.date.today().year,
    user: UserRecord = Depends(get_current_user),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        entries = get_heatmap(conn, user_id=user.id, year=year)
    return {"data": [e.model_dump() for e in entries], "error": None}


@router.get("/weak-points")
def progress_weak_points(
    request: Request,
    user: UserRecord = Depends(get_current_user),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as conn:
        points = get_weak_points(conn, user_id=user.id)
    return {"data": [p.model_dump() for p in points], "error": None}
