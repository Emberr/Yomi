"""Phase 1 content database initialization scaffold.

This script owns creation of content.db. It deliberately does not know about
user.db, auth tables, content source downloads, or real content ingestion.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

CONTENT_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class IngestionSettings:
    content_db_path: Path

    @classmethod
    def from_env(cls) -> "IngestionSettings":
        return cls(
            content_db_path=Path(os.getenv("DB_CONTENT_PATH", "/data/content.db"))
        )


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(connection: sqlite3.Connection) -> dict[str, object]:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA cache_size=-32000")
    journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    connection.execute("PRAGMA synchronous=NORMAL")
    synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    cache_size = connection.execute("PRAGMA cache_size").fetchone()[0]
    return {
        "journal_mode": journal_mode,
        "synchronous": synchronous,
        "foreign_keys": foreign_keys,
        "cache_size": cache_size,
    }


def initialize_content_db(path: Path) -> dict[str, object]:
    _ensure_parent(path)
    with sqlite3.connect(path) as connection:
        pragmas = _apply_pragmas(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS content_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO content_metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (CONTENT_SCHEMA_VERSION,),
        )
        connection.commit()

    return {
        "path": str(path),
        "schema_version": CONTENT_SCHEMA_VERSION,
        "pragmas": pragmas,
    }


def main() -> None:
    settings = IngestionSettings.from_env()
    result = initialize_content_db(settings.content_db_path)
    print(
        "Initialized content DB "
        f"{result['path']} with schema_version={result['schema_version']}"
    )


if __name__ == "__main__":
    main()

