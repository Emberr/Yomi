"""In-memory cache mapping active session IDs to derived encryption keys.

Keys live only in RAM. They are evicted on logout, session revocation, and
logout-everywhere. An expired or revoked session ID will never find a key here
because the auth dependency rejects it before the cache is consulted.
"""

from __future__ import annotations

import threading


class SessionKeyCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, bytes] = {}
        self._user_sessions: dict[int, set[str]] = {}

    def set(self, session_id: str, user_id: int, key: bytes) -> None:
        with self._lock:
            self._keys[session_id] = key
            self._user_sessions.setdefault(user_id, set()).add(session_id)

    def get(self, session_id: str) -> bytes | None:
        with self._lock:
            return self._keys.get(session_id)

    def drop(self, session_id: str) -> None:
        with self._lock:
            self._keys.pop(session_id, None)
            for sessions in self._user_sessions.values():
                sessions.discard(session_id)

    def drop_all_for_user(self, user_id: int) -> None:
        with self._lock:
            session_ids = self._user_sessions.pop(user_id, set())
            for sid in session_ids:
                self._keys.pop(sid, None)
