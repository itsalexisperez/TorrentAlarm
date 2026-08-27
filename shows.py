"""Versioned configuration for the shows monitored by TorrentAlarm."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Iterable


SHOWS_FILE = Path(__file__).with_name("shows.json")
MAX_RELEASE_OFFSET_MINUTES = 7 * 24 * 60


class ShowsConfigError(ValueError):
    """Raised when the shows configuration is invalid or cannot be saved."""


@dataclass(frozen=True)
class ShowConfig:
    show_id: int
    name: str
    season: int
    enabled: bool = True
    release_offset_minutes: int = 0


def validate_release_offset_minutes(value: Any) -> int:
    """Validate and return a release offset in the supported range."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or abs(value) > MAX_RELEASE_OFFSET_MINUTES
    ):
        raise ShowsConfigError(
            "release_offset_minutes must be an integer between "
            f"-{MAX_RELEASE_OFFSET_MINUTES} and {MAX_RELEASE_OFFSET_MINUTES}"
        )
    return value


def _validate_show(raw: Any, index: int) -> ShowConfig:
    if not isinstance(raw, dict):
        raise ShowsConfigError(f"show #{index} must be a JSON object")

    show_id = raw.get("show_id")
    name = raw.get("name")
    season = raw.get("season")
    enabled = raw.get("enabled")
    release_offset_minutes = raw.get("release_offset_minutes", 0)
    if isinstance(show_id, bool) or not isinstance(show_id, int) or show_id <= 0:
        raise ShowsConfigError(f"show #{index} show_id must be a positive integer")
    if not isinstance(name, str) or not name.strip():
        raise ShowsConfigError(f"show #{index} name must not be empty")
    if isinstance(season, bool) or not isinstance(season, int) or season <= 0:
        raise ShowsConfigError(f"show #{index} season must be a positive integer")
    if not isinstance(enabled, bool):
        raise ShowsConfigError(f"show #{index} enabled must be boolean")
    try:
        validate_release_offset_minutes(release_offset_minutes)
    except ShowsConfigError as error:
        raise ShowsConfigError(
            f"show #{index} release_offset_minutes must be an integer between "
            f"-{MAX_RELEASE_OFFSET_MINUTES} and {MAX_RELEASE_OFFSET_MINUTES}"
        ) from error
    return ShowConfig(show_id, name.strip(), season, enabled, release_offset_minutes)


def validate_shows(raw: Any) -> list[ShowConfig]:
    """Validate a decoded ``shows.json`` payload."""
    if not isinstance(raw, dict) or not isinstance(raw.get("shows"), list):
        raise ShowsConfigError("configuration must contain a shows array")

    shows: list[ShowConfig] = []
    seen_ids: set[int] = set()
    for index, item in enumerate(raw["shows"], start=1):
        show = _validate_show(item, index)
        if show.show_id in seen_ids:
            raise ShowsConfigError(f"duplicate show_id: {show.show_id}")
        seen_ids.add(show.show_id)
        shows.append(show)
    return shows


def load_shows(path: Path = SHOWS_FILE) -> list[ShowConfig]:
    """Load and validate the versioned shows configuration."""
    try:
        with path.open("r", encoding="utf-8") as config_file:
            raw = json.load(config_file)
    except FileNotFoundError as error:
        raise ShowsConfigError(f"configuration file not found: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ShowsConfigError(f"could not load shows configuration: {error}") from error
    return validate_shows(raw)


def save_shows(shows: Iterable[ShowConfig], path: Path = SHOWS_FILE) -> None:
    """Atomically write a validated shows configuration."""
    show_list = list(shows)
    payload = {
        "shows": [
            {
                "show_id": show.show_id,
                "name": show.name,
                "season": show.season,
                "enabled": show.enabled,
                "release_offset_minutes": show.release_offset_minutes,
            }
            for show in show_list
        ]
    }
    validate_shows(payload)
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
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise ShowsConfigError(f"could not save shows configuration: {error}") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
