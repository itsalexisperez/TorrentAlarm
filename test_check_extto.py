"""Unit tests for the EXTTO availability checker."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

import check_extto


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


class EXTTOTests(unittest.TestCase):
    def test_accent_insensitive_title_match(self) -> None:
        html = (
            '<table><tr><td><a class="torrent-title-link">'
            "Drag Race Espana S06E02 1080p WEB-DL"
            "</a></td></tr></table>"
        )
        with patch.object(
            check_extto.requests, "get", return_value=FakeResponse(html)
        ):
            result = check_extto.check_episode("Drag Race España", "S06E02")

        self.assertEqual(result, "Drag Race Espana S06E02 1080p WEB-DL")

    def test_current_mirror_is_used_after_legacy_mirror_fails(self) -> None:
        expected = "Drag Race Espana S06E02 1080p WEB-DL"
        html = (
            '<table><tr><td><a class="torrent-title-link">'
            f"{expected}"
            "</a></td></tr></table>"
        )
        with patch.object(
            check_extto.requests,
            "get",
            side_effect=[FakeResponse(status_code=403), FakeResponse(html)],
        ) as get:
            result = check_extto.check_episode("Drag Race España", "S06E02")

        self.assertEqual(result, expected)
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            ["https://ext.to/browse/", "https://extto.com/browse/"],
        )


if __name__ == "__main__":
    unittest.main()
