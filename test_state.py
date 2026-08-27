"""Automatic tests for notification state and its alarm_once integration."""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import requests

import alarm_once
from state import is_notified, load_state, mark_notified, save_state
from telegram_notify import TelegramNotificationError
from tvmaze import Episode


NOW = datetime(2026, 8, 27, 1, 5, tzinfo=timezone.utc)


def episode(code_season: int, code_number: int) -> Episode:
    return Episode(
        season=code_season,
        number=code_number,
        name=f"Episode {code_number}",
        airdate="2026-08-26",
        airtime="21:00",
        airstamp="2026-08-27T01:00:00+00:00",
    )


class StateTests(unittest.TestCase):
    def test_missing_state_starts_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            self.assertEqual(load_state(state_path), {})

    def test_mark_episode(self) -> None:
        state: dict[str, dict[str, bool]] = {}
        mark_notified(state, 68193, "S01E06")
        self.assertEqual(state, {"68193": {"S01E06": True}})

    def test_detect_already_marked_episode(self) -> None:
        state = {"68193": {"S01E06": True}}
        self.assertTrue(is_notified(state, 68193, "S01E06"))
        self.assertFalse(is_notified(state, 68193, "S01E07"))

    def test_multiple_episodes_same_series(self) -> None:
        state: dict[str, dict[str, bool]] = {}
        mark_notified(state, 68193, "S01E06")
        mark_notified(state, 68193, "S01E07")
        self.assertTrue(is_notified(state, 68193, "S01E06"))
        self.assertTrue(is_notified(state, 68193, "S01E07"))

    def test_multiple_series(self) -> None:
        state: dict[str, dict[str, bool]] = {}
        mark_notified(state, 68193, "S01E06")
        mark_notified(state, 12345, "S02E01")
        self.assertEqual(
            state,
            {"68193": {"S01E06": True}, "12345": {"S02E01": True}},
        )

    def test_skip_does_not_query_extto(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            save_state({"68193": {"S01E06": True}}, state_path)
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "check_episode"
            ) as check, patch.object(alarm_once, "send_message") as send:
                output = io.StringIO()
                with redirect_stdout(output):
                    result = alarm_once.run_once(NOW, state_path=state_path)

            self.assertEqual(result, 0)
            self.assertEqual(output.getvalue(), "SKIPPED_ALREADY_NOTIFIED: S01E06\n")
            check.assert_not_called()
            send.assert_not_called()

    def test_found_episode_sends_and_marks_notified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "check_episode", return_value="The Shards S01E06"
            ), patch.object(alarm_once, "send_message", return_value={}) as send:
                result = alarm_once.run_once(NOW, state_path=state_path)

            self.assertEqual(result, 0)
            send.assert_called_once_with(
                "🚨 TorrentAlarm\n\n"
                "The Shards S01E06 ya está disponible.\n\n"
                "Torrent detectado:\n"
                "The Shards S01E06"
            )
            self.assertTrue(is_notified(load_state(state_path), 68193, "S01E06"))

    def test_telegram_failure_does_not_mark_notified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with patch.object(alarm_once, "fetch_episodes", return_value=[episode(1, 6)]), patch.object(
                alarm_once, "check_episode", return_value="The Shards S01E06"
            ), patch.object(
                alarm_once,
                "send_message",
                side_effect=TelegramNotificationError("temporary failure"),
            ) as send:
                result = alarm_once.run_once(NOW, state_path=state_path)

            self.assertEqual(result, 1)
            send.assert_called_once()
            self.assertFalse(is_notified(load_state(state_path), 68193, "S01E06"))

    def test_multiple_simultaneous_episodes_are_sent_and_saved(self) -> None:
        episodes = [episode(1, 6), episode(1, 7)]
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with patch.object(alarm_once, "fetch_episodes", return_value=episodes), patch.object(
                alarm_once, "check_episode", side_effect=["Torrent 6", "Torrent 7"]
            ), patch.object(alarm_once, "send_message", return_value={}) as send:
                result = alarm_once.run_once(NOW, state_path=state_path)

            self.assertEqual(result, 0)
            self.assertEqual(send.call_count, 2)
            saved_state = load_state(state_path)
            self.assertTrue(is_notified(saved_state, 68193, "S01E06"))
            self.assertTrue(is_notified(saved_state, 68193, "S01E07"))

    def test_one_episode_failure_does_not_stop_the_others(self) -> None:
        episodes = [episode(1, 6), episode(1, 7)]
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with patch.object(alarm_once, "fetch_episodes", return_value=episodes), patch.object(
                alarm_once,
                "check_episode",
                side_effect=[requests.RequestException("EXTTO unavailable"), "Torrent 7"],
            ), patch.object(alarm_once, "send_message", return_value={}) as send:
                result = alarm_once.run_once(NOW, state_path=state_path)

            self.assertEqual(result, 1)
            send.assert_called_once()
            saved_state = load_state(state_path)
            self.assertFalse(is_notified(saved_state, 68193, "S01E06"))
            self.assertTrue(is_notified(saved_state, 68193, "S01E07"))

    def test_dry_run_does_not_modify_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state_path.write_text(
                json.dumps({"68193": {"S01E99": True}}, indent=2) + "\n",
                encoding="utf-8",
            )
            before = state_path.read_bytes()
            argv = [
                "alarm_once.py",
                "--dry-run",
                "--now",
                "2026-08-27T01:05:00+00:00",
            ]
            with patch.object(alarm_once, "STATE_FILE", state_path), patch.object(
                alarm_once, "fetch_episodes", return_value=[episode(1, 6)]
            ), patch.object(
                alarm_once, "check_episode", return_value="The Shards S01E06"
            ), patch.object(sys, "argv", argv):
                output = io.StringIO()
                with redirect_stdout(output):
                    result = alarm_once.main()

            self.assertEqual(result, 0)
            self.assertEqual(
                output.getvalue(),
                "FOUND: S01E06 | The Shards S01E06\n"
                "DRY_RUN: Telegram message for S01E06:\n"
                "🚨 TorrentAlarm\n\n"
                "The Shards S01E06 ya está disponible.\n\n"
                "Torrent detectado:\n"
                "The Shards S01E06\n",
            )
            self.assertEqual(state_path.read_bytes(), before)
            self.assertFalse(is_notified(load_state(state_path), 68193, "S01E06"))


if __name__ == "__main__":
    unittest.main()
