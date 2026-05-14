"""In-memory auth rate limiting and account lockout helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

LOGIN_REGISTER_LIMIT = 20
IP_WINDOW = timedelta(minutes=1)
FAILED_LOGIN_LIMIT = 10
FAILED_LOGIN_WINDOW = timedelta(hours=1)
ACCOUNT_LOCKOUT_DURATION = timedelta(minutes=15)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AuthRateLimiter:
    now_func: object = utc_now
    attempts: dict[tuple[str, str], list[datetime]] = field(
        default_factory=lambda: defaultdict(list)
    )
    account_failures: dict[str, tuple[datetime, int]] = field(default_factory=dict)

    def now(self) -> datetime:
        return self.now_func()

    def allow_ip_attempt(self, *, action: str, ip_address: str | None) -> bool:
        key = (action, ip_address or "unknown")
        now = self.now()
        cutoff = now - IP_WINDOW
        recent = [attempt for attempt in self.attempts[key] if attempt > cutoff]
        if len(recent) >= LOGIN_REGISTER_LIMIT:
            self.attempts[key] = recent
            return False
        recent.append(now)
        self.attempts[key] = recent
        return True

    def account_failure_count(self, username: str) -> int:
        existing = self.account_failures.get(username)
        now = self.now()
        if existing is None or existing[0] <= now - FAILED_LOGIN_WINDOW:
            self.account_failures[username] = (now, 1)
            return 1
        window_start, count = existing
        count += 1
        self.account_failures[username] = (window_start, count)
        return count

    def clear_account_failures(self, username: str) -> None:
        self.account_failures.pop(username, None)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_optional_timestamp(value: object | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
