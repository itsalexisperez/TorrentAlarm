"""Persistent, atomically-written notification and season state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


STATE_FILE = Path(__file__).with_name("state.json")


class StateError(RuntimeError):
    """Raised when notification state cannot be read or written safely."""


State = dict[str, Any]


def _normalize_scheduler(raw_scheduler: Any) -> dict[str, Any] | None:
    """Validate scheduler metadata without weakening notification-state checks."""
    if raw_scheduler is None:
        return None
    if not isinstance(raw_scheduler, dict):
        raise StateError("state.scheduler must be an object")

    mode = raw_scheduler.get("mode")
    fingerprint = raw_scheduler.get("fingerprint")
    next_wake = raw_scheduler.get("next_wake")
    target = raw_scheduler.get("target")
    applied_at = raw_scheduler.get("applied_at")
    if mode not in {"ACTIVE_POLL", "NEXT_WAKE", "HEARTBEAT", "DISABLED"}:
        raise StateError("state.scheduler.mode is invalid")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise StateError("state.scheduler.fingerprint must not be empty")
    if next_wake is not None and not isinstance(next_wake, str):
        raise StateError("state.scheduler.next_wake must be a string or null")
    if not isinstance(target, dict):
        raise StateError("state.scheduler.target must be an object")
    if not isinstance(applied_at, str) or not applied_at:
        raise StateError("state.scheduler.applied_at must not be empty")
    return {
        "mode": mode,
        "fingerprint": fingerprint,
        "next_wake": next_wake,
        "target": target,
        "applied_at": applied_at,
    }


def _normalize_scheduler_preflight(raw_preflight: Any) -> dict[str, Any] | None:
    """Validate non-applied preflight/backoff metadata separately from applied data."""
    if raw_preflight is None:
        return None
    if not isinstance(raw_preflight, dict):
        raise StateError("state.scheduler_preflight must be an object")
    job_id = raw_preflight.get("job_id")
    title_verified = raw_preflight.get("title_verified")
    checked_at = raw_preflight.get("checked_at")
    if not isinstance(job_id, str) or not job_id.isdigit() or int(job_id) <= 0:
        raise StateError("state.scheduler_preflight.job_id is invalid")
    if not isinstance(title_verified, bool):
        raise StateError("state.scheduler_preflight.title_verified must be boolean")
    if not isinstance(checked_at, str) or not checked_at:
        raise StateError("state.scheduler_preflight.checked_at must not be empty")
    return {
        "job_id": str(int(job_id)),
        "title_verified": title_verified,
        "checked_at": checked_at,
    }


def _season_for(show_id: str, show_seasons: Mapping[int, int] | None) -> int:
    season = show_seasons.get(int(show_id)) if show_seasons else None
    if season is None:
        # Legacy state had no season. Runtime callers provide the authoritative
        # season from shows.json; 1 preserves standalone legacy reads.
        return 1
    return season


def _normalize_state(raw_state: Any, show_seasons: Mapping[int, int] | None) -> tuple[State, bool]:
    if not isinstance(raw_state, dict):
        raise StateError("state must be a JSON object")

    if "shows" in raw_state:
        raw_shows = raw_state["shows"]
        if not isinstance(raw_shows, dict):
            raise StateError("state.shows must be an object")
        normalized_shows: dict[str, dict[str, Any]] = {}
        for show_id, entry in raw_shows.items():
            if not isinstance(show_id, str) or not show_id.isdigit() or int(show_id) <= 0:
                raise StateError("state show IDs must be positive integer strings")
            if not isinstance(entry, dict):
                raise StateError("state show entries must be objects")
            season = entry.get("season")
            completed = entry.get("completed")
            notified = entry.get("notified")
            if isinstance(season, bool) or not isinstance(season, int) or season <= 0:
                raise StateError("state seasons must be positive integers")
            if not isinstance(completed, bool):
                raise StateError("state completed values must be boolean")
            if not isinstance(notified, dict) or not all(
                isinstance(code, str) and value is True for code, value in notified.items()
            ):
                raise StateError("state notified values must be true")
            normalized_shows[str(int(show_id))] = {
                "season": season,
                "completed": completed,
                "notified": dict(notified),
            }
        normalized: State = {"shows": normalized_shows}
        if "scheduler" in raw_state:
            scheduler = _normalize_scheduler(raw_state["scheduler"])
            if scheduler is not None:
                normalized["scheduler"] = scheduler
        if "scheduler_preflight" in raw_state:
            preflight = _normalize_scheduler_preflight(raw_state["scheduler_preflight"])
            if preflight is not None:
                normalized["scheduler_preflight"] = preflight
        return normalized, raw_state != normalized

    migrated_shows: dict[str, dict[str, Any]] = {}
    for show_id, episodes in raw_state.items():
        if not isinstance(show_id, str) or not show_id.isdigit() or int(show_id) <= 0:
            raise StateError("legacy state must map positive show IDs to episode objects")
        if not isinstance(episodes, dict) or not all(
            isinstance(code, str) and value is True for code, value in episodes.items()
        ):
            raise StateError("legacy episode state values must be true")
        migrated_shows[str(int(show_id))] = {
            "season": _season_for(show_id, show_seasons),
            "completed": False,
            "notified": dict(episodes),
        }
    return {"shows": migrated_shows}, True


def load_state_with_migration(
    path: Path = STATE_FILE,
    show_seasons: Mapping[int, int] | None = None,
) -> tuple[State, bool]:
    """Load state and return ``(normalized_state, needs_persisting)``."""
    try:
        with path.open("r", encoding="utf-8") as state_file:
            raw_state: Any = json.load(state_file)
    except FileNotFoundError:
        return {"shows": {}}, True
    except (OSError, json.JSONDecodeError) as error:
        raise StateError(f"could not load state: {error}") from error
    return _normalize_state(raw_state, show_seasons)


def load_state(path: Path = STATE_FILE) -> State:
    """Load state, accepting both the current and legacy formats."""
    state, _ = load_state_with_migration(path)
    return state


def ensure_show(state: State, show_id: int, season: int) -> bool:
    """Ensure a show entry exists; return whether state was changed."""
    shows = state.setdefault("shows", {})
    key = str(show_id)
    entry = shows.get(key)
    if entry is None:
        shows[key] = {"season": season, "completed": False, "notified": {}}
        return True
    if entry["season"] != season:
        entry["season"] = season
        entry["completed"] = False
        return True
    return False


def is_notified(state: State, show_id: int, episode_code: str) -> bool:
    """Return whether an episode is already marked as notified."""
    entry = state.get("shows", {}).get(str(show_id), {})
    return entry.get("notified", {}).get(episode_code, False) is True


def mark_notified(state: State, show_id: int, episode_code: str) -> None:
    """Mark one episode as notified in the in-memory state."""
    entry = state.setdefault("shows", {}).setdefault(
        str(show_id), {"season": 1, "completed": False, "notified": {}}
    )
    entry.setdefault("notified", {})[episode_code] = True


def is_completed(state: State, show_id: int, season: int) -> bool:
    entry = state.get("shows", {}).get(str(show_id), {})
    return entry.get("season") == season and entry.get("completed") is True


def set_completed(state: State, show_id: int, season: int, completed: bool) -> bool:
    """Set completion and return whether the value changed."""
    entry = state["shows"][str(show_id)]
    changed = entry["season"] != season or entry["completed"] is not completed
    entry["season"] = season
    entry["completed"] = completed
    return changed


def save_state(state: State, path: Path = STATE_FILE) -> None:
    """Atomically save state so an interrupted write cannot corrupt it."""
    if not isinstance(state, dict) or not isinstance(state.get("shows"), dict):
        raise StateError("state must use the current shows schema before saving")
    if "scheduler" in state:
        _normalize_scheduler(state["scheduler"])
    if "scheduler_preflight" in state:
        _normalize_scheduler_preflight(state["scheduler_preflight"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(state, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise StateError(f"could not save state: {error}") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
