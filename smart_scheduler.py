"""Pure Smart Scheduler decisions for the TorrentAlarm cron job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Mapping, Sequence

from shows import ShowConfig
from state import State, is_notified
from temporal import effective_airstamp
from tvmaze import Episode


ACTIVE_WINDOW = timedelta(hours=12)
# Match alarm_once.py so the scheduler keeps retrying recently aired,
# unnotified episodes after the normal premiere window.
RECOVERY_WINDOW = timedelta(hours=48)
ACTIVE_EXPIRES_MARGIN = timedelta(minutes=15)
HEARTBEAT_MINUTE = 17
POLL_MINUTES = list(range(0, 60, 5))


@dataclass(frozen=True)
class EpisodeRef:
    show_id: int
    code: str
    airstamp: datetime


@dataclass(frozen=True)
class ScheduleDecision:
    mode: str
    pending: tuple[EpisodeRef, ...]
    next_wake: datetime | None
    active_until: datetime | None
    fingerprint: str
    target: dict[str, object]
    reason: str


def parse_airstamp(value: str | None) -> datetime | None:
    """Backward-compatible scheduler alias for the shared timestamp parser."""
    parsed = effective_airstamp(value)
    return parsed.astimezone(timezone.utc) if parsed is not None else None


def _utc_now(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must include a timezone offset")
    return now.astimezone(timezone.utc)


def _ceil_minute(value: datetime) -> datetime:
    original = value.astimezone(timezone.utc)
    floored = original.replace(second=0, microsecond=0)
    return floored + timedelta(minutes=1) if original > floored else floored


def _expires_at(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))


def _schedule(
    *,
    expires_at: int,
    hours: list[int],
    minutes: list[int],
    mdays: list[int],
    months: list[int],
    wdays: list[int],
) -> dict[str, object]:
    return {
        "timezone": "UTC",
        "expiresAt": expires_at,
        "hours": hours,
        "mdays": mdays,
        "minutes": minutes,
        "months": months,
        "wdays": wdays,
    }


def _target_for(
    mode: str,
    *,
    next_wake: datetime | None = None,
    active_until: datetime | None = None,
) -> dict[str, object]:
    if mode == "DISABLED":
        return {"enabled": False}

    if mode == "ACTIVE_POLL":
        if active_until is None:
            raise ValueError("ACTIVE_POLL requires active_until")
        schedule = _schedule(
            expires_at=_expires_at(active_until + ACTIVE_EXPIRES_MARGIN),
            hours=[-1],
            minutes=POLL_MINUTES,
            mdays=[-1],
            months=[-1],
            wdays=[-1],
        )
    elif mode == "NEXT_WAKE":
        if next_wake is None:
            raise ValueError("NEXT_WAKE requires next_wake")
        schedule = _schedule(
            # The exact date prevents this from becoming annual. Repeating the
            # remaining five-minute slots in the target hour gives the external
            # trigger a conservative recovery window if one dispatch fails.
            expires_at=_expires_at(next_wake + ACTIVE_WINDOW + ACTIVE_EXPIRES_MARGIN),
            hours=[next_wake.hour],
            minutes=list(range(next_wake.minute, 60, 5)),
            mdays=[next_wake.day],
            months=[next_wake.month],
            wdays=[-1],
        )
    elif mode == "HEARTBEAT":
        schedule = _schedule(
            expires_at=0,
            hours=[0],
            minutes=[HEARTBEAT_MINUTE],
            mdays=[-1],
            months=[-1],
            wdays=[-1],
        )
    else:
        raise ValueError(f"unknown scheduler mode: {mode}")

    return {"enabled": True, "schedule": schedule}


def _fingerprint(
    mode: str, target: dict[str, object], shows: Sequence[ShowConfig]
) -> str:
    show_configuration = [
        {
            "show_id": show.show_id,
            "season": show.season,
            "enabled": show.enabled,
            "release_offset_minutes": show.release_offset_minutes,
        }
        for show in shows
    ]
    encoded = json.dumps(
        {"mode": mode, "target": target, "shows": show_configuration},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decide(
    now: datetime,
    shows: Sequence[ShowConfig],
    episodes_by_show: Mapping[int, Sequence[Episode]],
    state: State,
) -> ScheduleDecision:
    """Calculate the desired cron schedule without network or filesystem access."""
    current = _utc_now(now)
    enabled_shows = [show for show in shows if show.enabled]
    pending: list[EpisodeRef] = []
    future: list[datetime] = []
    active_until: datetime | None = None

    for show in enabled_shows:
        for episode in episodes_by_show.get(show.show_id, ()):
            if episode.season != show.season:
                continue
            premiere = effective_airstamp(
                episode.airstamp, show.release_offset_minutes
            )
            if premiere is not None:
                premiere = premiere.astimezone(timezone.utc)
            if premiere is None:
                continue
            if premiere > current:
                future.append(premiere)
                continue
            if premiere <= current < premiere + RECOVERY_WINDOW:
                active_until = max(active_until, premiere + RECOVERY_WINDOW) if active_until else premiere + RECOVERY_WINDOW
                if not is_notified(state, show.show_id, episode.code):
                    pending.append(EpisodeRef(show.show_id, episode.code, premiere))

    if pending:
        mode = "ACTIVE_POLL"
        next_wake = None
        reason = f"{len(pending)} episode(s) pending notification (active/recovery window)"
    elif future:
        mode = "NEXT_WAKE"
        next_wake = _ceil_minute(min(future))
        reason = f"next known episode at {next_wake.isoformat()}"
    elif enabled_shows:
        mode = "HEARTBEAT"
        next_wake = None
        reason = "enabled shows have no future episode with a valid airstamp"
    else:
        mode = "DISABLED"
        next_wake = None
        reason = "all shows are disabled"

    target = _target_for(mode, next_wake=next_wake, active_until=active_until)
    return ScheduleDecision(
        mode=mode,
        pending=tuple(sorted(pending, key=lambda item: (item.airstamp, item.show_id, item.code))),
        next_wake=next_wake,
        active_until=active_until,
        fingerprint=_fingerprint(mode, target, shows),
        target=target,
        reason=reason,
    )
