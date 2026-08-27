"""Watch active TVMaze episodes and check their pending EXTTO torrents."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import time
from collections.abc import Callable

import requests

from check_extto import check_episode
from telegram_notify import TelegramNotificationError, send_message
from tvmaze import Episode, TVMazeError, fetch_episodes


SERIES_NAME = "The Shards"
SHOW_ID = 68193
DEFAULT_INTERVAL = 300.0
DEFAULT_MAX_MINUTES = 180.0
ACTIVE_WINDOW = timedelta(hours=3)


def parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("--now must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone offset")
    return parsed


def active_at(episode: Episode, now: datetime) -> bool:
    """Return whether an episode is in its three-hour premiere window."""
    if not episode.airstamp:
        return False
    try:
        premiere = parse_timestamp(episode.airstamp)
    except ValueError:
        return False
    current = now.astimezone(premiere.tzinfo)
    return premiere <= current < premiere + ACTIVE_WINDOW


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="seconds between EXTTO checks (default: 300)",
    )
    parser.add_argument(
        "--max-minutes",
        type=float,
        default=DEFAULT_MAX_MINUTES,
        help="maximum watch duration in minutes (default: 180)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="never send Telegram (Telegram is not connected yet)",
    )
    parser.add_argument(
        "--now",
        metavar="ISO_TIMESTAMP",
        help="simulate the current time for selecting active episodes",
    )
    return parser


def validate_arguments(args: argparse.Namespace) -> None:
    if args.interval <= 0:
        raise ValueError("--interval must be greater than zero")
    if args.max_minutes <= 0:
        raise ValueError("--max-minutes must be greater than zero")


def notification_message(episode: Episode, title: str) -> str:
    return (
        "🚨 TorrentAlarm\n\n"
        f"{SERIES_NAME} {episode.code} ya está disponible.\n\n"
        "Torrent detectado:\n"
        f"{title}"
    )


def run(
    args: argparse.Namespace,
    *,
    monotonic: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    validate_arguments(args)
    simulated_now = parse_timestamp(args.now) if args.now else None
    episodes = fetch_episodes(SHOW_ID)
    initial_now = simulated_now or datetime.now(timezone.utc)
    active_episodes = [episode for episode in episodes if active_at(episode, initial_now)]
    found: set[str] = set()
    clock = monotonic or time.monotonic
    sleep = sleeper or time.sleep
    deadline = clock() + args.max_minutes * 60

    if not active_episodes:
        print("ALL_FOUND")
        return 0

    while len(found) < len(active_episodes) and clock() < deadline:
        pending = [episode for episode in active_episodes if episode.code not in found]
        for episode in pending:
            try:
                title = check_episode(SERIES_NAME, episode.code)
            except requests.RequestException as error:
                description = str(error).splitlines()[0].strip() or error.__class__.__name__
                print(f"ERROR: {episode.code} | {description[:240]}")
                return 1

            if title is None:
                print(f"NOT_FOUND: {episode.code}")
            else:
                print(f"FOUND: {episode.code} | {title}")
                message = notification_message(episode, title)
                if args.dry_run:
                    print(f"DRY_RUN: Telegram message for {episode.code}:\n{message}")
                    found.add(episode.code)
                    continue

                try:
                    send_message(message)
                except TelegramNotificationError as error:
                    print(f"ERROR: Telegram failed for {episode.code}: {error}")
                    continue
                found.add(episode.code)

        if len(found) == len(active_episodes):
            print("ALL_FOUND")
            return 0

        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleep(min(args.interval, remaining))

    if active_episodes and len(found) < len(active_episodes):
        print("MAX_TIME_REACHED")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run(args)
    except (TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
