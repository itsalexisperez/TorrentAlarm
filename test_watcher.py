"""Automatic tests for watcher notification behavior."""

from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import unittest
from unittest.mock import Mock, patch

import watcher
from telegram_notify import TelegramNotificationError
from tvmaze import Episode


NOW = datetime(2026, 8, 27, 1, 5, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def episode(number: int) -> Episode:
    return Episode(
        season=1,
        number=number,
        name=f"Episode {number}",
        airdate="2026-08-26",
        airtime="21:00",
        airstamp="2026-08-27T01:00:00+00:00",
    )


def args(*, dry_run: bool = False, max_minutes: float = 0.1) -> object:
    return watcher.build_parser().parse_args(
        [
            "--interval",
            "2",
            "--max-minutes",
            str(max_minutes),
            *( ["--dry-run"] if dry_run else []),
            "--now",
            "2026-08-27T01:05:00+00:00",
        ]
    )


class WatcherTests(unittest.TestCase):
    def test_not_found_does_not_send_telegram(self) -> None:
        clock = FakeClock()
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6)]), patch.object(
            watcher, "check_episode", return_value=None
        ), patch.object(watcher, "send_message") as send:
            with redirect_stdout(io.StringIO()):
                watcher.run(args(dry_run=True), monotonic=clock.monotonic, sleeper=clock.sleep)
        send.assert_not_called()

    def test_found_sends_one_notification(self) -> None:
        clock = FakeClock()
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6)]), patch.object(
            watcher, "check_episode", return_value="The Shards S01E06"
        ), patch.object(watcher, "send_message") as send:
            with redirect_stdout(io.StringIO()):
                result = watcher.run(args(), monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result, 0)
        send.assert_called_once_with(
            "🚨 TorrentAlarm\n\n"
            "The Shards S01E06 ya está disponible.\n\n"
            "Torrent detectado:\n"
            "The Shards S01E06"
        )

    def test_found_episode_is_not_queried_again(self) -> None:
        clock = FakeClock()
        extto = Mock(side_effect=["The Shards S01E06", None, "The Shards S01E07"])
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6), episode(7)]), patch.object(
            watcher, "check_episode", extto
        ), patch.object(watcher, "send_message") as send:
            with redirect_stdout(io.StringIO()):
                result = watcher.run(args(), monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result, 0)
        self.assertEqual(extto.call_args_list[0].args, ("The Shards", "S01E06"))
        self.assertEqual(extto.call_args_list[1].args, ("The Shards", "S01E07"))
        self.assertEqual(extto.call_args_list[2].args, ("The Shards", "S01E07"))
        self.assertEqual(send.call_count, 2)

    def test_two_episodes_send_independent_notifications(self) -> None:
        clock = FakeClock()
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6), episode(7)]), patch.object(
            watcher, "check_episode", side_effect=["Torrent 6", "Torrent 7"]
        ), patch.object(watcher, "send_message") as send:
            with redirect_stdout(io.StringIO()):
                result = watcher.run(args(), monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result, 0)
        self.assertEqual(send.call_count, 2)
        self.assertIn("The Shards S01E06", send.call_args_list[0].args[0])
        self.assertIn("The Shards S01E07", send.call_args_list[1].args[0])

    def test_telegram_failure_keeps_episode_pending(self) -> None:
        clock = FakeClock()
        send = Mock(
            side_effect=[
                TelegramNotificationError("temporary failure"),
                None,
            ]
        )
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6)]), patch.object(
            watcher, "check_episode", return_value="Torrent 6"
        ), patch.object(watcher, "send_message", send):
            with redirect_stdout(io.StringIO()):
                result = watcher.run(args(), monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result, 0)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(clock.sleeps, [2.0])

    def test_all_found_terminates_without_sleep(self) -> None:
        clock = FakeClock()
        output = io.StringIO()
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6), episode(7)]), patch.object(
            watcher, "check_episode", side_effect=["Torrent 6", "Torrent 7"]
        ), patch.object(watcher, "send_message"), redirect_stdout(output):
            result = watcher.run(args(), monotonic=clock.monotonic, sleeper=clock.sleep)
        self.assertEqual(result, 0)
        self.assertEqual(clock.sleeps, [])
        self.assertTrue(output.getvalue().endswith("ALL_FOUND\n"))

    def test_dry_run_makes_zero_telegram_calls(self) -> None:
        clock = FakeClock()
        with patch.object(watcher, "fetch_episodes", return_value=[episode(6)]), patch.object(
            watcher, "check_episode", return_value="Torrent 6"
        ), patch.object(watcher, "send_message") as send:
            with redirect_stdout(io.StringIO()):
                result = watcher.run(
                    args(dry_run=True), monotonic=clock.monotonic, sleeper=clock.sleep
                )
        self.assertEqual(result, 0)
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
