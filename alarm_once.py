"""Run one calendar-to-EZTV availability check and then exit."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from check_eztv import EZTVError, check_episode
from state import StateError, is_notified, load_state, mark_notified, save_state
from telegram_notify import TelegramNotificationError, send_message
from tvmaze import Episode, TVMazeError, fetch_episodes, fetch_imdb_id


SERIES_NAME = "The Shards"
SHOW_ID = 68193
ACTIVE_WINDOW = timedelta(hours=3)
STATE_FILE = Path(__file__).with_name("state.json")


def notification_message(episode: Episode, title: str) -> str:
    return (
        "🚨 TorrentAlarm\n\n"
        f"{SERIES_NAME} {episode.code} ya está disponible.\n\n"
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


def is_active(episode: Episode, now: datetime) -> bool:
    """Return whether an episode is within its three-hour premiere window."""
    if not episode.airstamp:
        return False

    try:
        premiere = datetime.fromisoformat(episode.airstamp.replace("Z", "+00:00"))
    except ValueError:
        return False

    if premiere.tzinfo is None:
        premiere = premiere.replace(tzinfo=timezone.utc)
    current = now.astimezone(premiere.tzinfo)
    return premiere <= current < premiere + ACTIVE_WINDOW


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="never send Telegram",
    )
    parser.add_argument(
        "--now",
        metavar="ISO_TIMESTAMP",
        help="simulate the current time using an ISO-8601 timestamp",
    )
    return parser


def run_once(
    now: datetime,
    dry_run: bool = False,
    state_path: Path = STATE_FILE,
) -> int:
    state = load_state(state_path)
    episodes = fetch_episodes(SHOW_ID)
    active_episodes = [episode for episode in episodes if is_active(episode, now)]
    state_changed = False
    had_errors = False
    imdb_id = fetch_imdb_id(SHOW_ID) if active_episodes else None

    for episode in active_episodes:
        if is_notified(state, SHOW_ID, episode.code):
            print(f"SKIPPED_ALREADY_NOTIFIED: {episode.code}")
            continue

        try:
            title = check_episode(SERIES_NAME, episode.code, imdb_id)
        except (EZTVError, requests.RequestException) as error:
            description = str(error).splitlines()[0].strip() or error.__class__.__name__
            print(f"ERROR: {episode.code} | {description[:240]}")
            had_errors = True
            continue

        if title is None:
            print(f"NOT_FOUND: {episode.code}")
        else:
            print(f"FOUND: {episode.code} | {title}")
            message = notification_message(episode, title)
            if dry_run:
                print(f"DRY_RUN: Telegram message for {episode.code}:\n{message}")
                continue

            try:
                send_message(message)
            except TelegramNotificationError as error:
                print(f"ERROR: Telegram failed for {episode.code}: {error}")
                had_errors = True
                continue

            mark_notified(state, SHOW_ID, episode.code)
            state_changed = True

    if state_changed and not dry_run:
        save_state(state, state_path)

    return 1 if had_errors else 0


def main() -> int:
    args = build_parser().parse_args()

    try:
        now = parse_now(args.now)
        return run_once(now, dry_run=args.dry_run, state_path=STATE_FILE)
    except (StateError, TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
