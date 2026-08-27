"""Offline tests for Smart Scheduler decisions, persistence, and API safety."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from cronjob_client import CronJobAPIError, CronJobClient
from shows import ShowConfig
from smart_scheduler import decide
from state import is_notified, load_state, mark_notified, save_state
from tvmaze import Episode
import reconcile_scheduler


UTC = timezone.utc
NOW = datetime(2026, 8, 27, 1, 5, tzinfo=UTC)


def episode(number: int, airstamp: str, season: int = 1) -> Episode:
    return Episode(
        season=season,
        number=number,
        name=f"Episode {number}",
        airdate=airstamp[:10],
        airtime=airstamp[11:16],
        airstamp=airstamp,
    )


def show(show_id: int = 68193, season: int = 1, enabled: bool = True) -> ShowConfig:
    return ShowConfig(show_id, f"Show {show_id}", season, enabled)


def write_shows(path: Path, shows: list[ShowConfig]) -> None:
    path.write_text(
        json.dumps(
            {
                "shows": [
                    {
                        "show_id": item.show_id,
                        "name": item.name,
                        "season": item.season,
                        "enabled": item.enabled,
                    }
                    for item in shows
                ]
            }
        ),
        encoding="utf-8",
    )


class SchedulerDecisionTests(unittest.TestCase):
    def test_no_enabled_show_is_disabled(self) -> None:
        decision = decide(NOW, [show(enabled=False)], {}, {"shows": {}})
        self.assertEqual(decision.mode, "DISABLED")
        self.assertFalse(decision.target["enabled"])

    def test_enabled_without_future_is_heartbeat(self) -> None:
        decision = decide(NOW, [show()], {68193: []}, {"shows": {}})
        self.assertEqual(decision.mode, "HEARTBEAT")
        self.assertEqual(decision.target["schedule"]["minutes"], [17])

    def test_future_episode_is_next_wake_in_utc(self) -> None:
        future = episode(8, "2026-08-27T03:05:10-03:00")
        decision = decide(NOW, [show()], {68193: [future]}, {"shows": {}})
        self.assertEqual(decision.mode, "NEXT_WAKE")
        self.assertEqual(decision.next_wake, datetime(2026, 8, 27, 6, 6, tzinfo=UTC))
        self.assertEqual(decision.target["schedule"]["timezone"], "UTC")
        self.assertEqual(decision.target["schedule"]["minutes"], [6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56])

    def test_before_premiere_is_not_active(self) -> None:
        future = episode(8, "2026-08-27T01:06:00+00:00")
        self.assertEqual(decide(NOW, [show()], {68193: [future]}, {"shows": {}}).mode, "NEXT_WAKE")

    def test_premiere_exactly_is_active(self) -> None:
        current = episode(8, "2026-08-27T01:05:00+00:00")
        decision = decide(NOW, [show()], {68193: [current]}, {"shows": {}})
        self.assertEqual(decision.mode, "ACTIVE_POLL")
        self.assertEqual([item.code for item in decision.pending], ["S01E08"])

    def test_active_until_last_second_is_active(self) -> None:
        current = episode(8, "2026-08-26T13:06:00+00:00")
        at_last_second = datetime(2026, 8, 27, 1, 5, 59, tzinfo=UTC)
        decision = decide(at_last_second, [show()], {68193: [current]}, {"shows": {}})
        self.assertEqual(decision.mode, "ACTIVE_POLL")

    def test_at_twelve_hours_is_not_active(self) -> None:
        ended = episode(8, "2026-08-26T13:05:00+00:00")
        decision = decide(NOW, [show()], {68193: [ended]}, {"shows": {}})
        self.assertEqual(decision.mode, "HEARTBEAT")

    def test_active_already_notified_does_not_poll(self) -> None:
        state = {"shows": {"68193": {"season": 1, "completed": False, "notified": {"S01E08": True}}}}
        decision = decide(
            NOW, [show()], {68193: [episode(8, "2026-08-27T01:00:00+00:00")]}, state
        )
        self.assertEqual(decision.mode, "HEARTBEAT")
        self.assertEqual(decision.pending, ())

    def test_one_pending_show_wins_over_other_future_show(self) -> None:
        decisions = decide(
            NOW,
            [show(), show(44458, 4)],
            {
                68193: [episode(8, "2026-08-27T01:00:00+00:00")],
                44458: [episode(1, "2026-09-01T01:00:00+00:00", season=4)],
            },
            {"shows": {"68193": {"season": 1, "completed": False, "notified": {}}}},
        )
        self.assertEqual(decisions.mode, "ACTIVE_POLL")

    def test_disabled_show_is_ignored(self) -> None:
        future = episode(1, "2026-09-01T01:00:00+00:00")
        decision = decide(NOW, [show(enabled=False)], {68193: [future]}, {"shows": {}})
        self.assertEqual(decision.mode, "DISABLED")

    def test_expiration_is_after_active_window(self) -> None:
        current = episode(8, "2026-08-27T01:00:00+00:00")
        decision = decide(NOW, [show()], {68193: [current]}, {"shows": {}})
        self.assertEqual(decision.target["schedule"]["expiresAt"], 20260827131500)

    def test_month_and_year_boundaries_are_encoded(self) -> None:
        future = episode(8, "2027-01-01T00:00:30+00:00")
        now = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
        decision = decide(now, [show()], {68193: [future]}, {"shows": {}})
        schedule = decision.target["schedule"]
        self.assertEqual(decision.next_wake, datetime(2027, 1, 1, 0, 1, tzinfo=UTC))
        self.assertEqual(schedule["months"], [1])
        self.assertEqual(schedule["mdays"], [1])


class SchedulerReconcileTests(unittest.TestCase):
    def test_same_fingerprint_makes_zero_patches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path, shows_path = Path(directory) / "state.json", Path(directory) / "shows.json"
            write_shows(shows_path, [show()])
            state = {"shows": {}}
            client = Mock()
            with patch.object(reconcile_scheduler, "fetch_episodes", return_value=[]):
                reconcile_scheduler.reconcile(NOW, state_path=state_path, shows_path=shows_path, client=client)
            client.patch_job.assert_called_once()
            client.reset_mock()
            with patch.object(reconcile_scheduler, "fetch_episodes", return_value=[]):
                reconcile_scheduler.reconcile(NOW, state_path=state_path, shows_path=shows_path, client=client)
            client.patch_job.assert_not_called()

    def test_transition_and_notification_reconcile_each_patch_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path, shows_path = Path(directory) / "state.json", Path(directory) / "shows.json"
            write_shows(shows_path, [show()])
            client = Mock()
            future = episode(8, "2026-08-27T03:00:00+00:00")
            with patch.object(reconcile_scheduler, "fetch_episodes", return_value=[future]):
                reconcile_scheduler.reconcile(NOW, state_path=state_path, shows_path=shows_path, client=client)
            active_now = datetime(2026, 8, 27, 3, 5, tzinfo=UTC)
            with patch.object(
                reconcile_scheduler, "fetch_episodes", return_value=[future]
            ):
                reconcile_scheduler.reconcile(active_now, state_path=state_path, shows_path=shows_path, client=client)
            self.assertEqual(client.patch_job.call_count, 2)
            state = load_state(state_path)
            mark_notified(state, 68193, "S01E08")
            save_state(state, state_path)
            with patch.object(reconcile_scheduler, "fetch_episodes", return_value=[future]):
                reconcile_scheduler.reconcile(
                    active_now, state_path=state_path, shows_path=shows_path, client=client
                )
            self.assertEqual(client.patch_job.call_count, 3)
            self.assertTrue(is_notified(load_state(state_path), 68193, "S01E08"))

    def test_failed_patch_does_not_mark_applied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path, shows_path = Path(directory) / "state.json", Path(directory) / "shows.json"
            write_shows(shows_path, [show()])
            client = Mock()
            client.patch_job.side_effect = CronJobAPIError("cron-job.org request timed out")
            with patch.object(reconcile_scheduler, "fetch_episodes", return_value=[]):
                result = reconcile_scheduler.reconcile(
                    NOW, state_path=state_path, shows_path=shows_path, client=client
                )
            self.assertEqual(result, 1)
            self.assertNotIn("scheduler", load_state(state_path))

    def test_api_failure_inputs_are_secret_safe_and_never_leak_key(self) -> None:
        secret = "do-not-print-this"
        for failure in (
            requests.Timeout(),
            requests.HTTPError(response=Mock(status_code=401)),
            requests.HTTPError(response=Mock(status_code=403)),
            requests.HTTPError(response=Mock(status_code=404)),
            requests.HTTPError(response=Mock(status_code=429)),
            requests.HTTPError(response=Mock(status_code=500)),
        ):
            session = Mock()
            response = Mock(status_code=500)
            response.raise_for_status.side_effect = failure
            session.request.return_value = response
            client = CronJobClient(secret, "123", session=session)
            with self.subTest(failure=failure.__class__.__name__), self.assertRaises(CronJobAPIError) as caught:
                client.patch_job({"enabled": True})
            self.assertNotIn(secret, str(caught.exception))

    def test_feature_flag_off_does_not_construct_client_or_fetch(self) -> None:
        with patch.object(reconcile_scheduler, "CronJobClient") as client, patch.object(
            reconcile_scheduler, "fetch_episodes"
        ) as fetch:
            with patch.dict(reconcile_scheduler.os.environ, {"SMART_SCHEDULER_ENABLED": "false"}):
                self.assertEqual(reconcile_scheduler.main(), 0)
        client.assert_not_called()
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
