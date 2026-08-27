"""Shared timezone-aware episode timestamp calculations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_airstamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 airstamp, returning a timezone-aware datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def effective_airstamp(
    airstamp: str | None, release_offset_minutes: int = 0
) -> datetime | None:
    """Return TVMaze's airstamp corrected for configured availability offset."""
    parsed = parse_airstamp(airstamp)
    if parsed is None:
        return None
    return parsed + timedelta(minutes=release_offset_minutes)
