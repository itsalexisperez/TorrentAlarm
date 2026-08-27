"""Run one multi-show calendar-to-EZTV availability check and then exit."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from check_eztv import EZTVError, check_episode
from shows import SHOWS_FILE, ShowConfig, ShowsConfigError, load_shows
from state import (
    StateError,
    ensure_show,
    is_completed,
    is_notified,
    load_state_with_migration,
    mark_notified,
    save_state,
    set_completed,
)
from temporal import effective_airstamp
from telegram_notify import TelegramNotificationError, send_message
from tvmaze import Episode, TVMazeError, fetch_episodes, fetch_imdb_id


ACTIVE_WINDOW_HOURS = 12
ACTIVE_WINDOW = timedelta(hours=ACTIVE_WINDOW_HOURS)
STATE_FILE = Path(__file__).with_name("state.json")


def notification_message(show: ShowConfig, episode: Episode, title: str) -> str:
    return (
        "🚨 TorrentAlarm\n\n"
        f"{show.name} {episode.code} ya está disponible.\n\n"
        "Torrent detectado:\n"
        f"{title}"
    )


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("--now must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone offset")
    return parsed


def is_active(
    episode: Episode, now: datetime, release_offset_minutes: int = 0
) -> bool:
    """Return whether an episode is within its 12-hour premiere window."""
    premiere = effective_airstamp(episode.airstamp, release_offset_minutes)
    if premiere is None:
        return False
    current = now.astimezone(premiere.tzinfo)
    return premiere <= current < premiere + ACTIVE_WINDOW


def is_season_completed(
    episodes: list[Episode],
    season: int,
    now: datetime,
    release_offset_minutes: int = 0,
) -> bool:
    """Apply conservative airstamp-based season completion rules."""
    season_episodes = [episode for episode in episodes if episode.season == season]
    if not season_episodes:
        return False

    timestamps: list[datetime] = []
    for episode in season_episodes:
        timestamp = effective_airstamp(episode.airstamp, release_offset_minutes)
        if timestamp is None:
            return False
        current = now.astimezone(timestamp.tzinfo)
        if timestamp > current:
            return False
        timestamps.append(timestamp)

    last_episode = max(timestamps)
    return now.astimezone(last_episode.tzinfo) >= last_episode + ACTIVE_WINDOW and not any(
        is_active(episode, now, release_offset_minutes) for episode in season_episodes
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="never send Telegram")
    parser.add_argument("--now", metavar="ISO_TIMESTAMP", help="simulate current time")
    return parser


def _show_seasons(shows: list[ShowConfig]) -> dict[int, int]:
    return {show.show_id: show.season for show in shows}


def run_once(
    now: datetime,
    dry_run: bool = False,
    state_path: Path = STATE_FILE,
    shows_path: Path = SHOWS_FILE,
) -> int:
    shows = load_shows(shows_path)
    state, migrated = load_state_with_migration(state_path, _show_seasons(shows))
    state_changed = migrated and not dry_run
    had_errors = False

    for show in shows:
        if not show.enabled:
            print(f"SKIPPED_DISABLED: {show.name}")
            continue

        if not dry_run:
            state_changed = ensure_show(state, show.show_id, show.season) or state_changed

        try:
            episodes = fetch_episodes(show.show_id)
        except (TVMazeError, requests.RequestException, ValueError) as error:
            description = str(error).splitlines()[0].strip() or error.__class__.__name__
            print(f"ERROR: {show.name} | TVMaze | {description[:240]}")
            had_errors = True
            continue

        completed = is_completed(state, show.show_id, show.season)
        if completed and not is_season_completed(
            episodes, show.season, now, show.release_offset_minutes
        ):
            if not dry_run:
                state_changed = set_completed(state, show.show_id, show.season, False) or state_changed
            completed = False

        if completed:
            print(f"SKIPPED_COMPLETED: {show.name}")
            continue

        active_episodes = [
            episode
            for episode in episodes
            if episode.season == show.season
            and is_active(episode, now, show.release_offset_minutes)
        ]
        pending_episodes = [
            episode
            for episode in active_episodes
            if not is_notified(state, show.show_id, episode.code)
        ]
        imdb_id: str | None = None
        if pending_episodes:
            try:
                imdb_id = fetch_imdb_id(show.show_id)
            except (TVMazeError, requests.RequestException, ValueError) as error:
                description = str(error).splitlines()[0].strip() or error.__class__.__name__
                print(f"ERROR: {show.name} | TVMaze IMDb | {description[:240]}")
                had_errors = True
                continue

        for episode in active_episodes:
            if is_notified(state, show.show_id, episode.code):
                print(f"SKIPPED_ALREADY_NOTIFIED: {show.name} {episode.code}")
                continue

            try:
                title = check_episode(show.name, episode.code, imdb_id)
            except (EZTVError, requests.RequestException) as error:
                description = str(error).splitlines()[0].strip() or error.__class__.__name__
                print(f"ERROR: {show.name} {episode.code} | EZTV | {description[:240]}")
                had_errors = True
                continue

            if title is None:
                print(f"NOT_FOUND: {show.name} {episode.code}")
                continue

            print(f"FOUND: {show.name} {episode.code} | {title}")
            message = notification_message(show, episode, title)
            if dry_run:
                print(f"DRY_RUN: Telegram message for {show.name} {episode.code}:\n{message}")
                continue

            try:
                send_message(message)
            except TelegramNotificationError as error:
                print(f"ERROR: Telegram failed for {show.name} {episode.code}: {error}")
                had_errors = True
                continue

            mark_notified(state, show.show_id, episode.code)
            state_changed = True

        if (
            is_season_completed(episodes, show.season, now, show.release_offset_minutes)
            and not dry_run
        ):
            state_changed = set_completed(state, show.show_id, show.season, True) or state_changed
            print(f"COMPLETED: {show.name} season {show.season}")

    if state_changed and not dry_run:
        save_state(state, state_path)

    return 1 if had_errors else 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run_once(parse_now(args.now), dry_run=args.dry_run)
    except (StateError, ShowsConfigError, TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
