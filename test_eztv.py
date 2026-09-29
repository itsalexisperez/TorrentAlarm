"""Unit tests for the EZTV availability checker."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

import check_eztv


class FakeResponse:
    def __init__(self, payload=None, status_code: int = 200, json_error: Exception | None = None):
        self.payload = payload
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


def response_for(*torrents: dict[str, object], imdb_id: str | None = "27543562") -> FakeResponse:
    payload: dict[str, object] = {"torrents": list(torrents), "torrents_count": len(torrents)}
    if imdb_id is not None:
        payload["imdb_id"] = imdb_id
    return FakeResponse(payload)


def torrent(title: str, season: int = 1, episode: int = 6) -> dict[str, object]:
    return {"title": title, "season": season, "episode": episode}


class EZTVTests(unittest.TestCase):
    def test_exact_episode_is_found(self) -> None:
        expected = "The Shards S01E06 1080p WEB-DL EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent(expected)),
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args_list[0].args[0], check_eztv.EZTV_API_URL)
        self.assertEqual(get.call_args.kwargs["params"]["imdb_id"], "27543562")

    def test_primary_403_uses_fallback(self) -> None:
        expected = "The Shards S01E06 1080p WEB-DL EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[
                FakeResponse(status_code=403),
                response_for(torrent(expected)),
            ],
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            [check_eztv.EZTV_API_URL, check_eztv.EZTV_FALLBACK_API_URL],
        )

    def test_primary_timeout_uses_fallback(self) -> None:
        expected = "The Shards S01E06 720p WEB-DL EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[requests.Timeout("primary timed out"), response_for(torrent(expected))],
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], check_eztv.EZTV_FALLBACK_API_URL)

    def test_primary_invalid_json_uses_fallback(self) -> None:
        expected = "The Shards S01E06 480p WEB-DL EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[
                FakeResponse(json_error=ValueError("not JSON")),
                response_for(torrent(expected)),
            ],
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], check_eztv.EZTV_FALLBACK_API_URL)

    def test_primary_connection_failure_uses_fallback(self) -> None:
        expected = "The Shards S01E06 1080p WEB-DL EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[requests.ConnectionError("primary unavailable"), response_for(torrent(expected))],
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], check_eztv.EZTV_FALLBACK_API_URL)

    def test_primary_invalid_structure_uses_fallback(self) -> None:
        expected = "The Shards S01E06 1080p WEB-DL EZTV"
        invalid_payload = {"imdb_id": "27543562", "torrents": {}}
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[FakeResponse(payload=invalid_payload), response_for(torrent(expected))],
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[1].args[0], check_eztv.EZTV_FALLBACK_API_URL)

    def test_both_mirrors_fail(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[FakeResponse(status_code=403), FakeResponse(status_code=500)],
        ) as get:
            with self.assertRaisesRegex(check_eztv.EZTVError, "all EZTV mirrors failed"):
                check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertEqual(get.call_count, 2)

    def test_recent_fallback_checks_current_catalog(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards S01E05 1080p EZTV", episode=5)),
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)
        self.assertEqual(get.call_count, 4)
        self.assertEqual(get.call_args_list[0].args[0], check_eztv.EZTV_API_URL)

    def test_recent_global_fallback_handles_provider_imdb_mismatch(self) -> None:
        expected = "Line of Fire 2026 S01E02 1080p HDTV x264-SYNCOPY EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            side_effect=[
                FakeResponse(payload={"imdb_id": "42496001", "torrents_count": 0}),
                response_for(torrent(expected, episode=2), imdb_id=None),
            ],
        ) as get:
            result = check_eztv.check_episode("Line of Fire", "S01E02", "42496001")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0].kwargs["params"]["imdb_id"], "42496001")
        self.assertNotIn("imdb_id", get.call_args_list[1].kwargs["params"])

    def test_nonexistent_episode_returns_none(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards S01E05 1080p EZTV", episode=5)),
        ):
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)

    def test_pack_is_rejected(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards Season 1 Pack")),
        ):
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)

    def test_range_is_rejected(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards S01E06-E07")),
        ):
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)

    def test_complete_season_is_rejected(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards Complete Season 1")),
        ):
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)

    def test_imdb_prefix_is_normalized(self) -> None:
        expected = "The Shards S01E06 720p EZTV"
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent(expected)),
        ) as get:
            result = check_eztv.check_episode("The Shards", "S01E06", "tt27543562")

        self.assertEqual(result, expected)
        self.assertEqual(get.call_args.kwargs["params"]["imdb_id"], "27543562")

    def test_invalid_or_missing_imdb_id_is_rejected(self) -> None:
        for imdb_id in (None, "", "tt", "abc", "123456"):
            with self.subTest(imdb_id=imdb_id), self.assertRaises(ValueError):
                check_eztv.check_episode("The Shards", "S01E06", imdb_id)

    def test_http_errors_are_reported(self) -> None:
        for status_code in (403, 500):
            with self.subTest(status_code=status_code), patch.object(
                check_eztv.requests,
                "get",
                return_value=FakeResponse(status_code=status_code),
            ):
                with self.assertRaisesRegex(
                    check_eztv.EZTVError, f"EZTV returned HTTP {status_code}"
                ):
                    check_eztv.check_episode("The Shards", "S01E06", "27543562")

    def test_invalid_json_is_reported(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=FakeResponse(json_error=ValueError("not JSON")),
        ):
            with self.assertRaisesRegex(check_eztv.EZTVError, "invalid JSON"):
                check_eztv.check_episode("The Shards", "S01E06", "27543562")

    def test_structured_episode_must_match_title(self) -> None:
        with patch.object(
            check_eztv.requests,
            "get",
            return_value=response_for(torrent("The Shards S01E07 720p EZTV")),
        ):
            result = check_eztv.check_episode("The Shards", "S01E06", "27543562")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
