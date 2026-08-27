"""Check whether EZTV has one exact episode for a TV show."""

from __future__ import annotations

import re
from typing import Any

import requests


EZTV_API_URL = "https://eztvx.to/api/get-torrents"
REQUEST_TIMEOUT = 20
DEFAULT_LIMIT = 100

EPISODE_INPUT_RE = re.compile(
    r"^S(?P<season>[0-9]{2})E(?P<episode>[0-9]{2})$", re.IGNORECASE
)
EPISODE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])S(?P<season>[0-9]{2})[ ._-]*E(?P<episode>[0-9]{2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
EPISODE_RANGE_RE = re.compile(
    r"(?<![A-Za-z0-9])S[0-9]{2}[ ._-]*E[0-9]{2}"
    r"\s*(?:-|–|—|to|&|\+)\s*"
    r"(?:S[0-9]{2}[ ._-]*)?E[0-9]{2}(?![A-Za-z0-9])",
    re.IGNORECASE,
)


class EZTVError(RuntimeError):
    """Raised when the EZTV response cannot be used safely."""


def _normalize_name(value: str) -> list[str]:
    value = value.casefold()
    value = re.sub(r"[._-]+", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().split()


def _normalize_imdb_id(value: str | int | None) -> str:
    if value is None or isinstance(value, bool):
        raise ValueError("IMDb ID is required")

    raw_value = str(value).strip()
    match = re.fullmatch(r"(?:tt)?([0-9]{7,})", raw_value, re.IGNORECASE)
    if match is None:
        raise ValueError("IMDb ID must contain at least seven digits, optionally prefixed by tt")
    return match.group(1)


def _episode_numbers(episode_code: str) -> tuple[int, int]:
    match = EPISODE_INPUT_RE.fullmatch(episode_code)
    if match is None:
        raise ValueError("episode must use the exact SxxExx format")

    season = int(match.group("season"))
    episode = int(match.group("episode"))
    if season <= 0 or episode <= 0:
        raise ValueError("episode season and number must be greater than zero")
    return season, episode


def _numeric_field(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    return None


def _title_matches(title: str, show_name: str, episode_code: str) -> bool:
    wanted_name = _normalize_name(show_name)
    actual_name = _normalize_name(title)
    if not wanted_name or not any(
        actual_name[index : index + len(wanted_name)] == wanted_name
        for index in range(len(actual_name))
    ):
        return False

    normalized_title = " ".join(actual_name)
    if re.search(r"\b(?:complete|full)\s+(?:season|series)\b", normalized_title):
        return False
    if re.search(
        r"\bseason\s+(?:[0-9]+|[ivxlcdm]+)\s+(?:pack|complete|full)\b",
        normalized_title,
    ):
        return False
    if EPISODE_RANGE_RE.search(title):
        return False

    matches = list(EPISODE_TOKEN_RE.finditer(title))
    if len(matches) != 1:
        return False

    match = matches[0]
    wanted = EPISODE_INPUT_RE.fullmatch(episode_code)
    assert wanted is not None
    return (
        match.group("season").casefold() == wanted.group("season").casefold()
        and match.group("episode").casefold() == wanted.group("episode").casefold()
    )


def _fetch_page(imdb_id: str, page: int) -> dict[str, Any]:
    try:
        response = requests.get(
            EZTV_API_URL,
            params={"imdb_id": imdb_id, "limit": DEFAULT_LIMIT, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise EZTVError("EZTV request timed out") from error
    except requests.HTTPError as error:
        raise EZTVError(f"EZTV returned HTTP {response.status_code}") from error
    except requests.RequestException as error:
        raise EZTVError("EZTV request failed") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise EZTVError("EZTV returned invalid JSON") from error

    if not isinstance(payload, dict):
        raise EZTVError("EZTV returned an unexpected JSON object")
    if not isinstance(payload.get("torrents"), list):
        raise EZTVError("EZTV returned an invalid torrent list")
    return payload


def check_episode(
    show_name: str,
    episode_code: str,
    imdb_id: str | int | None,
) -> str | None:
    """Return one exact EZTV title, or ``None`` when it is not available."""
    if not _normalize_name(show_name):
        raise ValueError("show name must not be empty")
    season, episode = _episode_numbers(episode_code)
    normalized_imdb_id = _normalize_imdb_id(imdb_id)

    page = 1
    while True:
        payload = _fetch_page(normalized_imdb_id, page)

        response_imdb_id = payload.get("imdb_id")
        if response_imdb_id is None:
            return None
        try:
            if _normalize_imdb_id(response_imdb_id) != normalized_imdb_id:
                raise EZTVError("EZTV returned a different IMDb ID than requested")
        except ValueError as error:
            raise EZTVError("EZTV returned an invalid IMDb ID") from error

        torrents = payload["torrents"]
        for torrent in torrents:
            if not isinstance(torrent, dict):
                continue

            torrent_season = _numeric_field(torrent.get("season"))
            torrent_episode = _numeric_field(torrent.get("episode"))
            title = torrent.get("title")
            if (
                torrent_season != season
                or torrent_episode != episode
                or not isinstance(title, str)
            ):
                continue
            if _title_matches(title, show_name, episode_code):
                return title

        total = _numeric_field(payload.get("torrents_count"))
        if not torrents or total is None or page * DEFAULT_LIMIT >= total:
            return None
        page += 1
