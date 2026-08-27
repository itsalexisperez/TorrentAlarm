"""Run one calendar-to-EXTTO availability check and then exit."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from check_extto import check_episode
from state import StateError, is_notified, load_state, mark_notified, save_state
from tvmaze import Episode, TVMazeError, fetch_episodes


SERIES_NAME = "The Shards"
SHOW_ID = 68193
ACTIVE_WINDOW = timedelta(hours=3)
STATE_FILE = Path(__file__).with_name("state.json")


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
        help="never send Telegram (Telegram is disabled in this one-shot integration)",
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

    for episode in active_episodes:
        if is_notified(state, SHOW_ID, episode.code):
            print(f"SKIPPED_ALREADY_NOTIFIED: {episode.code}")
            continue

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
            if not dry_run:
                mark_notified(state, SHOW_ID, episode.code)
                state_changed = True

    if state_changed and not dry_run:
        save_state(state, state_path)

    # Telegram is intentionally not called yet; --dry-run remains side-effect free.
    return 0


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
