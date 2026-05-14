"""SQLite-backed audit log helpers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    id: int
    user_id: int | None
    event_type: str
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any]


def record_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    user_id: int | None,
    ip_address: str | None,
    user_agent: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_log (
            user_id,
            event_type,
            ip_address,
            user_agent,
            details
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            event_type,
            ip_address,
            user_agent,
            json.dumps(details or {}, sort_keys=True),
        ),
    )


def list_audit_events(connection: sqlite3.Connection) -> list[AuditEvent]:
    rows = connection.execute(
        """
        SELECT id, user_id, event_type, ip_address, user_agent, details
        FROM audit_log
        ORDER BY id
        """
    ).fetchall()
    return [
        AuditEvent(
            id=int(row[0]),
            user_id=None if row[1] is None else int(row[1]),
            event_type=str(row[2]),
            ip_address=None if row[3] is None else str(row[3]),
            user_agent=None if row[4] is None else str(row[4]),
            details=json.loads(str(row[5])),
        )
        for row in rows
    ]
