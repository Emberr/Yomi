"""Runtime configuration for the Yomi backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    content_db_path: Path
    user_db_path: Path
    behind_https: bool
    base_url: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            content_db_path=Path(os.getenv("DB_CONTENT_PATH", "/data/content.db")),
            user_db_path=Path(os.getenv("DB_USER_PATH", "/data/user.db")),
            behind_https=_env_bool("YOMI_BEHIND_HTTPS", False),
            base_url=os.getenv("YOMI_BASE_URL", "http://localhost:8888"),
            log_level=os.getenv("YOMI_LOG_LEVEL", "INFO").upper(),
        )

