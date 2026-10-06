"""Check whether EXTTO has a torrent for one exact TV episode."""

from __future__ import annotations

import re
import sys
import unicodedata

import requests
from bs4 import BeautifulSoup


EXTTO_SEARCH_URL = "https://extto.com/browse/"
EXTTO_SEARCH_URLS = ("https://ext.to/browse/", EXTTO_SEARCH_URL)
REQUEST_TIMEOUT = 20
USER_AGENT = "TorrentAlarm/0.1 (read-only episode availability checker)"

EPISODE_INPUT_RE = re.compile(r"^S(?P<season>\d{2})E(?P<episode>\d{2})$", re.IGNORECASE)
EPISODE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])S(?P<season>\d{2})[ ._-]*E(?P<episode>\d{2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
EPISODE_RANGE_RE = re.compile(
    r"(?<![A-Za-z0-9])S\d{2}[ ._-]*E\d{2}"
    r"\s*(?:-|–|—|to|&|\+)\s*"
    r"(?:S\d{2}[ ._-]*)?E\d{2}(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def normalize_name(value: str) -> str:
    """Normalize name separators so dots, spaces, hyphens and underscores match."""
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    value = value.casefold()
    value = re.sub(r"[._-]+", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def contains_series_name(title: str, series_name: str) -> bool:
    wanted = normalize_name(series_name).split()
    actual = normalize_name(title).split()
    if not wanted:
        return False
    return any(actual[index : index + len(wanted)] == wanted for index in range(len(actual)))


def contains_exact_episode(title: str, episode: str) -> bool:
    """Require one standalone episode token and reject multi-episode packages."""
    wanted = EPISODE_INPUT_RE.fullmatch(episode)
    if not wanted:
        return False

    normalized_title = normalize_name(title)
    if re.search(r"\bcomplete\s+(?:season|series)\b", normalized_title):
        return False
    if re.search(r"\bseason\s+(?:\d+|[ivxlcdm]+)\s+pack\b", normalized_title):
        return False
    if EPISODE_RANGE_RE.search(title):
        return False

    matches = list(EPISODE_TOKEN_RE.finditer(title))
    if len(matches) != 1:
        return False

    match = matches[0]
    return (
        match.group("season").casefold() == wanted.group("season").casefold()
        and match.group("episode").casefold() == wanted.group("episode").casefold()
    )


def extract_title(title_link) -> str:
    """Read all visible text and undo spaces introduced between inline spans."""
    title = title_link.get_text(" ", strip=True)
    title = re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", title)
    title = re.sub(r"(?<=\w)\s+\.\s+(?=\w)", ".", title)
    return title


def find_first_valid_title(html: str, series_name: str, episode: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for row in soup.select("tr"):
        title_link = row.select_one("a.torrent-title-link")
        if title_link is None:
            continue

        title = extract_title(title_link)
        if contains_series_name(title, series_name) and contains_exact_episode(title, episode):
            return title

    return None


def check_episode(series_name: str, episode: str) -> str | None:
    """Return the first exact EXTTO title for an episode, if it exists."""
    last_error: requests.RequestException | None = None
    for endpoint in EXTTO_SEARCH_URLS:
        try:
            response = requests.get(
                endpoint,
                params={"q": f"{series_name} {episode}"},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            last_error = error
            continue

        title = find_first_valid_title(response.text, series_name, episode)
        if title is not None:
            return title

    if last_error is not None:
        raise last_error
    return None


def main() -> int:
    if len(sys.argv) != 3:
        print("ERROR")
        print('usage: python check_extto.py "Series Name" S01E06')
        return 2

    series_name, episode = sys.argv[1:]
    if not normalize_name(series_name):
        print("ERROR")
        print("series name is empty")
        return 2
    if not EPISODE_INPUT_RE.fullmatch(episode):
        print("ERROR")
        print("episode must use the exact SxxExx format")
        return 2

    try:
        title = check_episode(series_name, episode)
    except requests.RequestException as error:
        description = str(error).splitlines()[0].strip() or error.__class__.__name__
        print("ERROR")
        print(description[:240])
        return 1

    if title is None:
        print("NOT_FOUND")
    else:
        print("FOUND")
        print(title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
