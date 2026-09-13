"""EVE time formatting — EVE client uses UTC displayed as EVE time."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_eve_time(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return to_utc(dt).strftime("%Y.%m.%d %H:%M")


def next_sync_at(last_sync: datetime | None, interval_minutes: int) -> datetime | None:
    if last_sync is None:
        return None
    return to_utc(last_sync) + timedelta(minutes=max(1, interval_minutes))
