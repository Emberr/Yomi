"""FastAPI entrypoint for the Yomi backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from yomi import __version__
from yomi.auth.router import router as auth_router
from yomi.config import Settings
from yomi.db.sqlite import content_db_status, initialize_user_db, user_db_status


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        initialize_user_db(app_settings.user_db_path)
        yield

    app = FastAPI(title="Yomi API", version=__version__, lifespan=lifespan)
    app.state.settings = app_settings
    app.include_router(auth_router)

    @app.get("/api/health")
    def health() -> dict[str, object]:
        content_status = content_db_status(app_settings.content_db_path)
        user_status = user_db_status(app_settings.user_db_path)
        return {
            "status": "healthy",
            "version": __version__,
            "base_url": app_settings.base_url,
            "behind_https": app_settings.behind_https,
            "databases": {
                "content": content_status,
                "user": user_status,
            },
        }

    return app


app = create_app()
