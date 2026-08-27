"""Manage the versioned shows.json file without touching secrets or state."""

from __future__ import annotations

import argparse
from pathlib import Path

from shows import (
    SHOWS_FILE,
    ShowConfig,
    ShowsConfigError,
    load_shows,
    save_shows,
    validate_release_offset_minutes,
)
from tvmaze import TVMazeError, fetch_episodes, fetch_show, search_shows


class ManageShowsError(RuntimeError):
    """Raised for a clear, user-actionable CLI error."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=SHOWS_FILE, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="list configured shows")

    add = commands.add_parser("add", help="add a show after validating it with TVMaze")
    add.add_argument("name", help="show name to search")
    add.add_argument("--season", type=int, required=True)
    add.add_argument("--show-id", type=int)
    add.add_argument("--release-offset-minutes", type=int, default=0)

    set_offset = commands.add_parser("set-offset", help="set a show's release offset")
    set_offset.add_argument("name")
    set_offset.add_argument("--minutes", type=int, required=True)

    for command in ("disable", "enable"):
        action = commands.add_parser(command, help=f"{command} a configured show")
        action.add_argument("name")
    return parser


def _find_by_name(shows: list[ShowConfig], name: str) -> int:
    wanted = name.strip().casefold()
    for index, show in enumerate(shows):
        if show.name.casefold() == wanted:
            return index
    raise ManageShowsError(f"show not configured: {name}")


def _resolve_show(name: str, show_id: int | None):
    if show_id is not None:
        return fetch_show(show_id)
    results = search_shows(name)
    if not results:
        raise ManageShowsError(f"TVMaze found no show for: {name}")
    if len(results) > 1:
        choices = ", ".join(f"{result.name} ({result.show_id})" for result in results[:10])
        raise ManageShowsError(
            f"TVMaze returned multiple shows; use --show-id. Matches: {choices}"
        )
    return results[0]


def command_list(path: Path) -> int:
    for show in load_shows(path):
        status = "enabled" if show.enabled else "disabled"
        print(
            f"{show.name} | show_id={show.show_id} | season={show.season} | "
            f"release_offset_minutes={show.release_offset_minutes} | {status}"
        )
    return 0


def command_add(
    path: Path,
    name: str,
    season: int,
    show_id: int | None,
    release_offset_minutes: int,
) -> int:
    if season <= 0:
        raise ManageShowsError("season must be a positive integer")
    try:
        validate_release_offset_minutes(release_offset_minutes)
    except ShowsConfigError as error:
        raise ManageShowsError(str(error)) from error
    shows = load_shows(path)
    resolved = _resolve_show(name, show_id)
    if any(show.show_id == resolved.show_id for show in shows):
        raise ManageShowsError(f"show_id already configured: {resolved.show_id}")
    try:
        episodes = fetch_episodes(resolved.show_id)
    except (TVMazeError, ValueError) as error:
        raise ManageShowsError(f"could not validate season with TVMaze: {error}") from error
    if not any(episode.season == season for episode in episodes):
        raise ManageShowsError(
            f"TVMaze does not show season {season} for {resolved.name}"
        )
    shows.append(
        ShowConfig(resolved.show_id, resolved.name, season, True, release_offset_minutes)
    )
    save_shows(shows, path)
    print(
        f"ADDED: {resolved.name} | show_id={resolved.show_id} | season={season} | "
        f"release_offset_minutes={release_offset_minutes}"
    )
    return 0


def command_toggle(path: Path, name: str, enabled: bool) -> int:
    shows = load_shows(path)
    index = _find_by_name(shows, name)
    current = shows[index]
    shows[index] = ShowConfig(
        current.show_id,
        current.name,
        current.season,
        enabled,
        current.release_offset_minutes,
    )
    save_shows(shows, path)
    print(f"{'ENABLED' if enabled else 'DISABLED'}: {current.name}")
    return 0


def command_set_offset(path: Path, name: str, minutes: int) -> int:
    shows = load_shows(path)
    index = _find_by_name(shows, name)
    current = shows[index]
    shows[index] = ShowConfig(
        current.show_id, current.name, current.season, current.enabled, minutes
    )
    save_shows(shows, path)
    print(f"OFFSET_SET: {current.name} | release_offset_minutes={minutes}")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            return command_list(args.config)
        if args.command == "add":
            return command_add(
                args.config,
                args.name,
                args.season,
                args.show_id,
                args.release_offset_minutes,
            )
        if args.command == "set-offset":
            return command_set_offset(args.config, args.name, args.minutes)
        return command_toggle(args.config, args.name, args.command == "enable")
    except (ManageShowsError, ShowsConfigError, TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
