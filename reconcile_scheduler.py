"""Reconcile the external TorrentAlarm cron schedule after a normal check."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import requests

from cronjob_client import CronJobAPIError, CronJobClient
from shows import SHOWS_FILE, ShowsConfigError, load_shows
from smart_scheduler import decide
from state import STATE_FILE, StateError, load_state_with_migration, save_state
from tvmaze import TVMazeError, fetch_episodes


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


def is_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


PREFLIGHT_RETRY_AFTER = timedelta(hours=1)


def _preflight_backoff_active(preflight: object, job_id: str, now: datetime) -> bool:
    if not isinstance(preflight, dict):
        return False
    if preflight.get("job_id") != job_id or preflight.get("title_verified") is True:
        return False
    checked_at = preflight.get("checked_at")
    if not isinstance(checked_at, str):
        return False
    try:
        checked = datetime.fromisoformat(checked_at)
    except ValueError:
        return False
    return now.astimezone(timezone.utc) - checked.astimezone(timezone.utc) < PREFLIGHT_RETRY_AFTER


def reconcile(
    now: datetime,
    *,
    state_path: Path = STATE_FILE,
    shows_path: Path = SHOWS_FILE,
    client: CronJobClient,
) -> int:
    shows = load_shows(shows_path)
    state, migrated = load_state_with_migration(
        state_path, {show.show_id: show.season for show in shows}
    )
    preflight = state.get("scheduler_preflight")
    preflight_verified = (
        isinstance(preflight, dict)
        and preflight.get("job_id") == client.job_id
        and preflight.get("title_verified") is True
    )
    if not preflight_verified and _preflight_backoff_active(preflight, client.job_id, now):
        print("ERROR: scheduler preflight is in backoff; retrying later")
        return 1
    if not preflight_verified:
        try:
            job = client.get_job()
        except CronJobAPIError as error:
            state["scheduler_preflight"] = {
                "job_id": client.job_id,
                "title_verified": False,
                "checked_at": now.astimezone(timezone.utc).isoformat(),
            }
            save_state(state, state_path)
            print(f"ERROR: scheduler preflight failed: {error}")
            return 1
        state["scheduler_preflight"] = {
            "job_id": client.job_id,
            "title_verified": job.get("title") == "TorrentAlarm",
            "checked_at": now.astimezone(timezone.utc).isoformat(),
        }
        save_state(state, state_path)
        if job.get("title") != "TorrentAlarm":
            print("ERROR: scheduler preflight failed: job title is not TorrentAlarm")
            return 1
        schedule = job.get("schedule")
        expires_at = schedule.get("expiresAt") if isinstance(schedule, dict) else None
        print(
            "CRONJOB_PREFLIGHT: "
            f"jobId={job.get('jobId')} enabled={job.get('enabled')} "
            f"nextExecution={job.get('nextExecution')} schedule={schedule} "
            f"expiresAt={expires_at} status={job.get('lastStatus')}"
        )
    episodes_by_show: dict[int, list] = {}
    for show in shows:
        if not show.enabled:
            continue
        try:
            episodes_by_show[show.show_id] = fetch_episodes(show.show_id)
        except (TVMazeError, requests.RequestException, ValueError) as error:
            description = str(error).splitlines()[0].strip() or error.__class__.__name__
            print(f"ERROR: {show.name} | TVMaze scheduler input | {description[:240]}")
            return 1

    decision = decide(now, shows, episodes_by_show, state)
    applied = state.get("scheduler")
    if isinstance(applied, dict) and applied.get("fingerprint") == decision.fingerprint:
        print(f"SCHEDULE_UNCHANGED: {decision.mode} | {decision.reason}")
        if migrated:
            save_state(state, state_path)
        return 0

    try:
        client.patch_job(decision.target)
    except CronJobAPIError as error:
        print(f"ERROR: scheduler PATCH failed: {error}")
        return 1

    state["scheduler"] = {
        "mode": decision.mode,
        "fingerprint": decision.fingerprint,
        "next_wake": decision.next_wake.isoformat() if decision.next_wake else None,
        "target": decision.target,
        "applied_at": now.astimezone(timezone.utc).isoformat(),
    }
    save_state(state, state_path)
    print(f"SCHEDULE_PATCHED: {decision.mode} | {decision.reason}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--now", metavar="ISO_TIMESTAMP", help="simulate current time")
    return parser


def main() -> int:
    if not is_enabled(os.environ.get("SMART_SCHEDULER_ENABLED")):
        print("SMART_SCHEDULER_DISABLED")
        return 0

    api_key = os.environ.get("CRONJOB_API_KEY", "")
    job_id = os.environ.get("CRONJOB_JOB_ID", "")
    try:
        client = CronJobClient(api_key, job_id)
        return reconcile(parse_now(build_parser().parse_args().now), client=client)
    except (CronJobAPIError, StateError, ShowsConfigError, TVMazeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
