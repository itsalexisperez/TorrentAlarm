"""Read future episodes for a TVMaze show by its stable show ID."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
import sys
from typing import Any

import requests


TVMAZE_EPISODES_URL = "https://api.tvmaze.com/shows/{show_id}/episodes"
TVMAZE_SHOW_URL = "https://api.tvmaze.com/shows/{show_id}"
TVMAZE_SEARCH_URL = "https://api.tvmaze.com/search/shows"
REQUEST_TIMEOUT = 20
USER_AGENT = "TorrentAlarm/0.1 (TVMaze episode calendar reader)"
IMDB_ID_RE = re.compile(r"(?:tt)?(?P<id>[0-9]{7,})$", re.IGNORECASE)


class TVMazeError(RuntimeError):
    """Raised when TVMaze data cannot be retrieved or decoded."""


@dataclass(frozen=True)
class Episode:
    season: int
    number: int
    name: str
    airdate: str | None
    airtime: str | None
    airstamp: str | None

    @property
    def code(self) -> str:
        return f"S{self.season:02d}E{self.number:02d}"


@dataclass(frozen=True)
class Show:
    show_id: int
    name: str


def _episode_from_payload(payload: dict[str, Any]) -> Episode:
    return Episode(
        season=int(payload["season"]),
        number=int(payload["number"]),
        name=str(payload.get("name") or "(sin título)"),
        airdate=payload.get("airdate") or None,
        airtime=payload.get("airtime") or None,
        airstamp=payload.get("airstamp") or None,
    )


def fetch_episodes(show_id: int) -> list[Episode]:
    """Fetch and extract all episodes for a TVMaze show ID."""
    if show_id <= 0:
        raise ValueError("show ID must be a positive integer")

    try:
        response = requests.get(
            TVMAZE_EPISODES_URL.format(show_id=show_id),
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise TVMazeError("TVMaze request timed out") from error
    except requests.HTTPError as error:
        raise TVMazeError(f"TVMaze returned HTTP {response.status_code}") from error
    except requests.RequestException as error:
        raise TVMazeError("TVMaze request failed") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise TVMazeError("TVMaze returned invalid JSON") from error

    if not isinstance(payload, list):
        raise TVMazeError("TVMaze returned an unexpected episode list")

    try:
        return [_episode_from_payload(item) for item in payload]
    except (KeyError, TypeError, ValueError) as error:
        raise TVMazeError("TVMaze returned an invalid episode") from error


def fetch_imdb_id(show_id: int) -> str:
    """Fetch a show's IMDb ID and return it in EZTV's numeric format."""
    if show_id <= 0:
        raise ValueError("show ID must be a positive integer")

    try:
        response = requests.get(
            TVMAZE_SHOW_URL.format(show_id=show_id),
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise TVMazeError("TVMaze show request timed out") from error
    except requests.HTTPError as error:
        raise TVMazeError(f"TVMaze returned HTTP {response.status_code} for show") from error
    except requests.RequestException as error:
        raise TVMazeError("TVMaze show request failed") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise TVMazeError("TVMaze returned invalid show JSON") from error

    if not isinstance(payload, dict):
        raise TVMazeError("TVMaze returned an unexpected show object")
    externals = payload.get("externals")
    raw_imdb_id = externals.get("imdb") if isinstance(externals, dict) else None
    if not isinstance(raw_imdb_id, str):
        raise TVMazeError("TVMaze show has no IMDb ID")

    match = IMDB_ID_RE.fullmatch(raw_imdb_id.strip())
    if match is None:
        raise TVMazeError("TVMaze show returned an invalid IMDb ID")
    return match.group("id")


def fetch_show(show_id: int) -> Show:
    """Fetch canonical show metadata by its stable TVMaze ID."""
    if show_id <= 0:
        raise ValueError("show ID must be a positive integer")
    try:
        response = requests.get(
            TVMAZE_SHOW_URL.format(show_id=show_id),
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise TVMazeError("TVMaze show request timed out") from error
    except requests.HTTPError as error:
        raise TVMazeError(f"TVMaze returned HTTP {response.status_code} for show") from error
    except requests.RequestException as error:
        raise TVMazeError("TVMaze show request failed") from error
    try:
        payload = response.json()
    except ValueError as error:
        raise TVMazeError("TVMaze returned invalid show JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int):
        raise TVMazeError("TVMaze returned an invalid show")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise TVMazeError("TVMaze show has no name")
    return Show(payload["id"], name.strip())


def search_shows(query: str) -> list[Show]:
    """Search TVMaze and return the matching canonical show records."""
    if not query.strip():
        raise ValueError("show name must not be empty")
    try:
        response = requests.get(
            TVMAZE_SEARCH_URL,
            params={"q": query.strip()},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise TVMazeError("TVMaze search timed out") from error
    except requests.HTTPError as error:
        raise TVMazeError(f"TVMaze search returned HTTP {response.status_code}") from error
    except requests.RequestException as error:
        raise TVMazeError("TVMaze search failed") from error
    try:
        payload = response.json()
    except ValueError as error:
        raise TVMazeError("TVMaze returned invalid search JSON") from error
    if not isinstance(payload, list):
        raise TVMazeError("TVMaze returned an invalid search result")

    results: list[Show] = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("show"), dict):
            continue
        show = item["show"]
        if isinstance(show.get("id"), int) and isinstance(show.get("name"), str):
            results.append(Show(show["id"], show["name"].strip()))
    return results


def _parse_airstamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_future_episode(episode: Episode, now: datetime | None = None) -> bool:
    """Return whether an episode is now or in the future.

    A missing or unparsable airstamp falls back to airdate. In that case,
    episodes dated today are retained because their exact time is unknown.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    if episode.airstamp:
        timestamp = _parse_airstamp(episode.airstamp)
        if timestamp is not None:
            return timestamp >= current.astimezone(timestamp.tzinfo)

    if episode.airdate:
        try:
            return date.fromisoformat(episode.airdate) >= current.date()
        except ValueError:
            return False

    return False


def format_episode(episode: Episode) -> str:
    """Format an episode while preserving all calendar fields."""
    airdate = episode.airdate or "desconocida"
    airtime = episode.airtime or "desconocida"
    airstamp = episode.airstamp or "desconocido (hora desconocida)"
    return (
        f"{episode.code} | {episode.name} | "
        f"airdate={airdate} | airtime={airtime} | airstamp={airstamp}"
    )


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("ERROR")
        print("usage: python tvmaze.py SHOW_ID")
        return 2

    show_id = int(sys.argv[1])
    try:
        episodes = fetch_episodes(show_id)
    except (TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1

    for episode in episodes:
        if is_future_episode(episode):
            print(format_episode(episode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
