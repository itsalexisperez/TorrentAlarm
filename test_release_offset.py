"""Offline coverage for configurable release availability offsets."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import alarm_once
import manage_shows
from shows import ShowConfig, ShowsConfigError, load_shows, save_shows
from smart_scheduler import decide
from state import is_notified, load_state, save_state
from temporal import effective_airstamp
from tvmaze import Episode, Show


UTC = timezone.utc


def episode(number: int = 1, airstamp: str = "2026-09-02T12:00:00Z", season: int = 4) -> Episode:
    return Episode(season, number, "Episode", airstamp[:10], airstamp[11:16], airstamp)


class ConfigOffsetTests(unittest.TestCase):
    def load(self, value: object):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shows.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_shows(path)

    def test_omitted_offset_defaults_to_zero(self) -> None:
        shows = self.load({"shows": [{"show_id": 1, "name": "Example", "season": 1, "enabled": True}]})
        self.assertEqual(shows[0].release_offset_minutes, 0)

    def test_zero_negative_and_positive_offsets_are_valid(self) -> None:
        for offset in (0, -660, 60):
            with self.subTest(offset=offset):
                shows = self.load(
                    {"shows": [{"show_id": 1, "name": "Example", "season": 1, "enabled": True,
                                  "release_offset_minutes": offset}]}
                )
                self.assertEqual(shows[0].release_offset_minutes, offset)

    def test_invalid_offset_types_and_range_are_rejected(self) -> None:
        for offset in ("-660", -660.0, True, 10081, -10081):
            with self.subTest(offset=offset), self.assertRaises(ShowsConfigError):
                self.load(
                    {"shows": [{"show_id": 1, "name": "Example", "season": 1, "enabled": True,
                                  "release_offset_minutes": offset}]}
                )


class EffectiveAirstampTests(unittest.TestCase):
    def test_effective_timestamp_preserves_timezone_and_applies_offset(self) -> None:
        original = "2026-09-02T12:00:00Z"
        self.assertEqual(effective_airstamp(original, 0), datetime(2026, 9, 2, 12, tzinfo=UTC))
        self.assertEqual(effective_airstamp(original, -660), datetime(2026, 9, 2, 1, tzinfo=UTC))
        self.assertEqual(effective_airstamp(original, 60), datetime(2026, 9, 2, 13, tzinfo=UTC))
        self.assertIsNotNone(effective_airstamp("2026-09-02T12:00:00-03:00", 60).tzinfo)


class AlarmOffsetTests(unittest.TestCase):
    def test_active_window_uses_effective_timestamp(self) -> None:
        item = episode()
        for now, expected in (
            ("2026-09-02T00:59:59Z", False),
            ("2026-09-02T01:00:00Z", True),
            ("2026-09-02T12:59:59Z", True),
            ("2026-09-02T13:00:00Z", False),
        ):
            with self.subTest(now=now):
                self.assertEqual(
                    alarm_once.is_active(item, datetime.fromisoformat(now.replace("Z", "+00:00")), -660),
                    expected,
                )

    def test_completion_uses_effective_window_end(self) -> None:
        item = episode(airstamp="2026-09-02T12:00:00Z")
        before = datetime(2026, 9, 2, 12, 59, 59, tzinfo=UTC)
        at_end = datetime(2026, 9, 2, 13, 0, tzinfo=UTC)
        self.assertFalse(alarm_once.is_season_completed([item], 4, before, -660))
        self.assertTrue(alarm_once.is_season_completed([item], 4, at_end, -660))

    def test_deduplication_is_unchanged_when_offset_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            save_shows([ShowConfig(44458, "Ted Lasso", 4, True, -660)], shows_path)
            original_state = {
                "shows": {"44458": {"season": 4, "completed": False, "notified": {"S04E01": True}}}
            }
            save_state(original_state, state_path)
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode()]), patch.object(
                alarm_once, "check_episode"
            ) as check:
                result = alarm_once.run_once(
                    datetime(2026, 9, 2, 1, 5, tzinfo=UTC),
                    dry_run=True,
                    state_path=state_path,
                    shows_path=shows_path,
                )
            self.assertEqual(result, 0)
            check.assert_not_called()
            self.assertTrue(is_notified(load_state(state_path), 44458, "S04E01"))


class SchedulerOffsetTests(unittest.TestCase):
    def test_next_wake_uses_effective_timestamp(self) -> None:
        show = ShowConfig(44458, "Ted Lasso", 4, True, -660)
        decision = decide(
            datetime(2026, 9, 1, tzinfo=UTC), [show], {44458: [episode()]}, {"shows": {}},
        )
        self.assertEqual(decision.mode, "NEXT_WAKE")
        self.assertEqual(decision.next_wake, datetime(2026, 9, 2, 1, tzinfo=UTC))

    def test_active_poll_and_expiration_use_effective_timestamp(self) -> None:
        show = ShowConfig(44458, "Ted Lasso", 4, True, -660)
        decision = decide(
            datetime(2026, 9, 2, 1, tzinfo=UTC), [show], {44458: [episode()]}, {"shows": {}},
        )
        self.assertEqual(decision.mode, "ACTIVE_POLL")
        self.assertEqual(decision.active_until, datetime(2026, 9, 4, 1, tzinfo=UTC))
        self.assertEqual(decision.target["schedule"]["expiresAt"], 20260904011500)

    def test_offset_is_part_of_fingerprint_even_without_known_episodes(self) -> None:
        now = datetime(2026, 9, 1, tzinfo=UTC)
        zero = decide(now, [ShowConfig(44458, "Ted Lasso", 4)], {44458: []}, {"shows": {}})
        early = decide(now, [ShowConfig(44458, "Ted Lasso", 4, True, -660)], {44458: []}, {"shows": {}})
        self.assertEqual(zero.mode, early.mode)
        self.assertNotEqual(zero.fingerprint, early.fingerprint)

    def test_multiple_shows_can_have_distinct_offsets(self) -> None:
        shows = [
            ShowConfig(1, "Show 1", 1, True, 0),
            ShowConfig(2, "Show 2", 1, True, -60),
        ]
        episodes = {
            1: [episode(1, "2026-09-02T03:00:00Z", 1)],
            2: [episode(1, "2026-09-02T04:00:00Z", 1)],
        }
        decision = decide(datetime(2026, 9, 1, tzinfo=UTC), shows, episodes, {"shows": {}})
        self.assertEqual(decision.next_wake, datetime(2026, 9, 2, 3, tzinfo=UTC))


class ManageOffsetTests(unittest.TestCase):
    def test_add_and_set_offset_preserve_config_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shows.json"
            state_path = Path(directory) / "state.json"
            save_shows([], path)
            state = {"shows": {"44458": {"season": 4, "completed": False, "notified": {"S04E01": True}}}}
            save_state(state, state_path)
            with patch.object(manage_shows, "search_shows", return_value=[Show(44458, "Ted Lasso")]), patch.object(
                manage_shows, "fetch_episodes", return_value=[episode()]
            ):
                self.assertEqual(
                    manage_shows.run(
                        ["--config", str(path), "add", "Ted Lasso", "--season", "4",
                         "--release-offset-minutes", "-660"]
                    ),
                    0,
                )
            self.assertEqual(load_shows(path)[0].release_offset_minutes, -660)
            self.assertEqual(manage_shows.run(["--config", str(path), "set-offset", "Ted Lasso", "--minutes", "60"]), 0)
            self.assertEqual(load_shows(path)[0].release_offset_minutes, 60)
            self.assertEqual(load_state(state_path), state)


if __name__ == "__main__":
    unittest.main()
