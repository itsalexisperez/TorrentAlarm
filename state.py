"""Persistent notification state for TorrentAlarm."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


STATE_FILE = Path(__file__).with_name("state.json")


class StateError(RuntimeError):
    """Raised when notification state cannot be read or written safely."""


def load_state(path: Path = STATE_FILE) -> dict[str, dict[str, bool]]:
    """Load notification state, returning an empty state when the file is absent."""
    try:
        with path.open("r", encoding="utf-8") as state_file:
            raw_state: Any = json.load(state_file)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        raise StateError(f"could not load state: {error}") from error

    if not isinstance(raw_state, dict):
        raise StateError("state must be a JSON object")

    state: dict[str, dict[str, bool]] = {}
    for show_id, episodes in raw_state.items():
        if not isinstance(show_id, str) or not isinstance(episodes, dict):
            raise StateError("state must map show IDs to episode objects")
        if not all(isinstance(code, str) and value is True for code, value in episodes.items()):
            raise StateError("episode state values must be true")
        state[show_id] = dict(episodes)
    return state


def is_notified(state: dict[str, dict[str, bool]], show_id: int, episode_code: str) -> bool:
    """Return whether an episode is already marked as notified."""
    return state.get(str(show_id), {}).get(episode_code, False) is True


def mark_notified(
    state: dict[str, dict[str, bool]], show_id: int, episode_code: str
) -> None:
    """Mark one episode as notified in the in-memory state."""
    state.setdefault(str(show_id), {})[episode_code] = True


def save_state(state: dict[str, dict[str, bool]], path: Path = STATE_FILE) -> None:
    """Atomically save state so an interrupted write does not corrupt the file."""
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
