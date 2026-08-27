"""Unit tests for the versioned multi-show configuration."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from shows import ShowsConfigError, load_shows


class ShowsConfigTests(unittest.TestCase):
    def load(self, payload: object):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shows.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_shows(path)

    def test_valid_config_supports_two_shows(self) -> None:
        shows = self.load(
            {
                "shows": [
                    {"show_id": 68193, "name": "The Shards", "season": 1, "enabled": True},
                    {"show_id": 44458, "name": "Ted Lasso", "season": 4, "enabled": True},
                ]
            }
        )
        self.assertEqual([show.show_id for show in shows], [68193, 44458])

    def test_disabled_show_is_valid(self) -> None:
        shows = self.load(
            {"shows": [{"show_id": 1, "name": "Example", "season": 2, "enabled": False}]}
        )
        self.assertFalse(shows[0].enabled)

    def test_invalid_fields_are_rejected(self) -> None:
        cases = (
            {"show_id": 0, "name": "Example", "season": 1, "enabled": True},
            {"show_id": 1, "name": "", "season": 1, "enabled": True},
            {"show_id": 1, "name": "Example", "season": 0, "enabled": True},
            {"show_id": 1, "name": "Example", "season": 1, "enabled": 1},
        )
        for show in cases:
            with self.subTest(show=show), self.assertRaises(ShowsConfigError):
                self.load({"shows": [show]})

    def test_duplicate_show_id_is_rejected(self) -> None:
        show = {"show_id": 1, "name": "Example", "season": 1, "enabled": True}
        with self.assertRaisesRegex(ShowsConfigError, "duplicate"):
            self.load({"shows": [show, dict(show, name="Other")]})


if __name__ == "__main__":
    unittest.main()
