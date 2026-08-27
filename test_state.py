"""Tests for notification state, migration, and alarm_once invariants."""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import alarm_once
from shows import ShowConfig
from state import (
    ensure_show,
    is_notified,
    load_state,
    load_state_with_migration,
    mark_notified,
    save_state,
)
from telegram_notify import TelegramNotificationError
from tvmaze import Episode, TVMazeError


NOW = datetime(2026, 8, 27, 1, 5, tzinfo=timezone.utc)


def episode(season: int, number: int, premiere: str = "2026-08-27T01:00:00+00:00") -> Episode:
    return Episode(
        season=season,
        number=number,
        name=f"Episode {number}",
        airdate=premiere[:10],
        airtime="01:00",
        airstamp=premiere,
    )


def write_shows(path: Path, *shows: ShowConfig) -> None:
    path.write_text(
        json.dumps(
            {
                "shows": [
                    {
                        "show_id": show.show_id,
                        "name": show.name,
                        "season": show.season,
                        "enabled": show.enabled,
                    }
                    for show in shows
                ]
            }
        ),
        encoding="utf-8",
    )


class StateTests(unittest.TestCase):
    def test_active_window_boundaries(self) -> None:
        premiere = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
        for label, now, expected in (
            ("before", premiere - timedelta(minutes=1), False),
            ("inside", premiere + timedelta(hours=11, minutes=59), True),
            ("boundary", premiere + timedelta(hours=12), False),
        ):
            with self.subTest(label=label):
                self.assertEqual(alarm_once.is_active(episode(1, 6), now), expected)

    def test_missing_state_starts_empty_current_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_state(Path(directory) / "state.json"), {"shows": {}})

    def test_mark_episode(self) -> None:
        state = {"shows": {}}
        ensure_show(state, 68193, 1)
        mark_notified(state, 68193, "S01E06")
        self.assertTrue(is_notified(state, 68193, "S01E06"))
        self.assertEqual(state["shows"]["68193"]["notified"], {"S01E06": True})

    def test_multiple_series(self) -> None:
        state = {"shows": {}}
        ensure_show(state, 68193, 1)
        ensure_show(state, 44458, 4)
        mark_notified(state, 68193, "S01E06")
        mark_notified(state, 44458, "S04E01")
        self.assertTrue(is_notified(state, 68193, "S01E06"))
        self.assertTrue(is_notified(state, 44458, "S04E01"))

    def test_legacy_migration_preserves_real_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(
                json.dumps({"68193": {"S01E06": True, "S01E07": True}}), encoding="utf-8"
            )
            migrated, changed = load_state_with_migration(state_path, {68193: 1})
            self.assertTrue(changed)
            self.assertTrue(is_notified(migrated, 68193, "S01E06"))
            self.assertTrue(is_notified(migrated, 68193, "S01E07"))
            save_state(migrated, state_path)
            again, changed_again = load_state_with_migration(state_path, {68193: 1})
            self.assertFalse(changed_again)
            self.assertEqual(again, migrated)

    def test_telegram_failure_does_not_mark_notified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(shows_path, ShowConfig(68193, "The Shards", 1))
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "fetch_imdb_id", return_value="27543562"
            ), patch.object(alarm_once, "check_episode", return_value="The Shards S01E06"), patch.object(
                alarm_once,
                "send_message",
                side_effect=TelegramNotificationError("temporary failure"),
            ):
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 1)
            self.assertFalse(is_notified(load_state(state_path), 68193, "S01E06"))

    def test_success_marks_only_after_telegram_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(shows_path, ShowConfig(68193, "The Shards", 1))
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "fetch_imdb_id", return_value="27543562"
            ), patch.object(alarm_once, "check_episode", return_value="The Shards S01E06"), patch.object(
                alarm_once, "send_message", return_value={}
            ):
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 0)
            self.assertTrue(is_notified(load_state(state_path), 68193, "S01E06"))

    def test_dry_run_does_not_modify_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(shows_path, ShowConfig(68193, "The Shards", 1))
            before = state_path.read_bytes() if state_path.exists() else None
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "fetch_imdb_id", return_value="27543562"
            ), patch.object(alarm_once, "check_episode", return_value="The Shards S01E06"), patch.object(
                alarm_once, "send_message"
            ) as send:
                alarm_once.run_once(NOW, dry_run=True, state_path=state_path, shows_path=shows_path)
            send.assert_not_called()
            self.assertEqual(state_path.exists(), before is not None)

    def test_completed_show_skips_eztv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(shows_path, ShowConfig(68193, "The Shards", 1))
            save_state(
                {
                    "shows": {
                        "68193": {"season": 1, "completed": True, "notified": {}}
                    }
                },
                state_path,
            )
            old = episode(1, 1, "2026-08-20T01:00:00+00:00")
            with patch.object(alarm_once, "fetch_episodes", return_value=[old]), patch.object(
                alarm_once, "check_episode"
            ) as check:
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 0)
            check.assert_not_called()

    def test_one_series_error_does_not_block_another(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(
                shows_path,
                ShowConfig(68193, "The Shards", 1),
                ShowConfig(44458, "Ted Lasso", 4),
            )
            with patch.object(
                alarm_once,
                "fetch_episodes",
                side_effect=[TVMazeError("The Shards unavailable"), [episode(4, 1)]],
            ), patch.object(alarm_once, "fetch_imdb_id", return_value="12345678"), patch.object(
                alarm_once, "check_episode", return_value="Ted Lasso S04E01"
            ), patch.object(alarm_once, "send_message", return_value={} ) as send:
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 1)
            send.assert_called_once()
            self.assertTrue(is_notified(load_state(state_path), 44458, "S04E01"))

    def test_two_enabled_series_and_different_seasons_are_processed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(
                shows_path,
                ShowConfig(68193, "The Shards", 1),
                ShowConfig(44458, "Ted Lasso", 4),
            )
            shards_episodes = [episode(1, 6), episode(2, 1)]
            ted_episodes = [episode(3, 1), episode(4, 1)]
            with patch.object(
                alarm_once, "fetch_episodes", side_effect=[shards_episodes, ted_episodes]
            ), patch.object(
                alarm_once, "fetch_imdb_id", side_effect=["27543562", "12345678"]
            ) as resolve_imdb, patch.object(
                alarm_once, "check_episode", side_effect=["The Shards S01E06", "Ted Lasso S04E01"]
            ), patch.object(alarm_once, "send_message", return_value={}) as send:
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 0)
            self.assertEqual(resolve_imdb.call_count, 2)
            self.assertEqual(send.call_count, 2)
            saved = load_state(state_path)
            self.assertTrue(is_notified(saved, 68193, "S01E06"))
            self.assertTrue(is_notified(saved, 44458, "S04E01"))
            self.assertFalse(is_notified(saved, 68193, "S02E01"))

    def test_disabled_series_is_not_fetched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            shows_path = Path(directory) / "shows.json"
            write_shows(
                shows_path,
                ShowConfig(68193, "The Shards", 1, False),
                ShowConfig(44458, "Ted Lasso", 4, True),
            )
            with patch.object(alarm_once, "fetch_episodes", return_value=[]) as fetch:
                result = alarm_once.run_once(NOW, state_path=state_path, shows_path=shows_path)
            self.assertEqual(result, 0)
            fetch.assert_called_once_with(44458)


class CompletionTests(unittest.TestCase):
    def test_future_episode_prevents_completion(self) -> None:
        episodes = [episode(1, 1, "2026-08-20T01:00:00+00:00"), episode(1, 2, "2026-09-01T01:00:00+00:00")]
        self.assertFalse(alarm_once.is_season_completed(episodes, 1, NOW))

    def test_last_episode_younger_than_window_is_not_completed(self) -> None:
        episodes = [episode(1, 1, "2026-08-26T20:00:00+00:00")]
        self.assertFalse(alarm_once.is_season_completed(episodes, 1, NOW))

    def test_last_episode_older_than_window_is_completed(self) -> None:
        episodes = [episode(1, 1, "2026-08-26T12:00:00+00:00")]
        self.assertTrue(alarm_once.is_season_completed(episodes, 1, NOW))


if __name__ == "__main__":
    unittest.main()
