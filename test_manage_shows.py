"""Tests for the show-management CLI."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import manage_shows
from shows import ShowConfig, load_shows, save_shows
from tvmaze import Episode, Show


def episode(season: int) -> Episode:
    return Episode(season, 1, "Pilot", "2026-01-01", "00:00", "2026-01-01T00:00:00+00:00")


class ManageShowsTests(unittest.TestCase):
    def path_with(self, *shows: ShowConfig) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "shows.json"
        save_shows(shows, path)
        return directory, path

    def test_list(self) -> None:
        directory, path = self.path_with(ShowConfig(68193, "The Shards", 1, True))
        try:
            with patch("builtins.print") as output:
                self.assertEqual(manage_shows.run(["--config", str(path), "list"]), 0)
            output.assert_called_once_with(
                "The Shards | show_id=68193 | season=1 | "
                "release_offset_minutes=0 | enabled"
            )
        finally:
            directory.cleanup()

    def test_add_resolves_canonical_show_and_validates_season(self) -> None:
        directory, path = self.path_with()
        try:
            with patch.object(manage_shows, "search_shows", return_value=[Show(44458, "Ted Lasso")]), patch.object(
                manage_shows, "fetch_episodes", return_value=[episode(4)]
            ):
                self.assertEqual(manage_shows.run(["--config", str(path), "add", "Ted Lasso", "--season", "4"]), 0)
            self.assertEqual(load_shows(path), [ShowConfig(44458, "Ted Lasso", 4, True)])
        finally:
            directory.cleanup()

    def test_add_duplicate_is_rejected(self) -> None:
        directory, path = self.path_with(ShowConfig(44458, "Ted Lasso", 4, True))
        try:
            with patch.object(manage_shows, "search_shows", return_value=[Show(44458, "Ted Lasso")]), patch.object(
                manage_shows, "fetch_episodes"
            ) as fetch:
                self.assertEqual(manage_shows.run(["--config", str(path), "add", "Ted Lasso", "--season", "4"]), 1)
            fetch.assert_not_called()
        finally:
            directory.cleanup()

    def test_ambiguous_name_requires_show_id(self) -> None:
        directory, path = self.path_with()
        try:
            with patch.object(
                manage_shows,
                "search_shows",
                return_value=[Show(1, "The Office"), Show(2, "The Office")],
            ), patch.object(manage_shows, "fetch_episodes") as fetch:
                self.assertEqual(manage_shows.run(["--config", str(path), "add", "The Office", "--season", "1"]), 1)
            fetch.assert_not_called()
        finally:
            directory.cleanup()

    def test_nonexistent_season_is_rejected(self) -> None:
        directory, path = self.path_with()
        try:
            with patch.object(manage_shows, "search_shows", return_value=[Show(44458, "Ted Lasso")]), patch.object(
                manage_shows, "fetch_episodes", return_value=[episode(3)]
            ):
                self.assertEqual(manage_shows.run(["--config", str(path), "add", "Ted Lasso", "--season", "4"]), 1)
            self.assertEqual(load_shows(path), [])
        finally:
            directory.cleanup()

    def test_disable_and_enable_only_change_config(self) -> None:
        directory, path = self.path_with(ShowConfig(68193, "The Shards", 1, True))
        state_path = Path(directory.name) / "state.json"
        state_before = {"shows": {"68193": {"season": 1, "completed": False, "notified": {"S01E06": True}}}}
        state_path.write_text(json.dumps(state_before), encoding="utf-8")
        try:
            self.assertEqual(manage_shows.run(["--config", str(path), "disable", "The Shards"]), 0)
            self.assertFalse(load_shows(path)[0].enabled)
            self.assertEqual(manage_shows.run(["--config", str(path), "enable", "The Shards"]), 0)
            self.assertTrue(load_shows(path)[0].enabled)
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), state_before)
        finally:
            directory.cleanup()

    def test_invalid_config_is_reported(self) -> None:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "shows.json"
        path.write_text("{invalid", encoding="utf-8")
        try:
            self.assertEqual(manage_shows.run(["--config", str(path), "list"]), 1)
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
