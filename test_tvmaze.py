"""Unit tests for TVMaze show metadata lookups."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

import tvmaze


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


class TVMazeShowTests(unittest.TestCase):
    def test_search_shows_extracts_canonical_results(self) -> None:
        response = FakeResponse(
            [
                {"score": 1, "show": {"id": 44458, "name": "Ted Lasso"}},
                {"score": 0.5, "show": {"id": 99, "name": "Ted"}},
            ]
        )
        with patch.object(tvmaze.requests, "get", return_value=response) as get:
            result = tvmaze.search_shows("Ted Lasso")
        self.assertEqual(result[0].show_id, 44458)
        self.assertEqual(get.call_args.kwargs["params"], {"q": "Ted Lasso"})

    def test_fetch_show_returns_canonical_metadata(self) -> None:
        response = FakeResponse({"id": 44458, "name": "Ted Lasso"})
        with patch.object(tvmaze.requests, "get", return_value=response):
            self.assertEqual(tvmaze.fetch_show(44458), tvmaze.Show(44458, "Ted Lasso"))

    def test_fetch_imdb_id_normalizes_prefix(self) -> None:
        response = FakeResponse({"externals": {"imdb": "tt27543562"}})
        with patch.object(tvmaze.requests, "get", return_value=response) as get:
            result = tvmaze.fetch_imdb_id(68193)

        self.assertEqual(result, "27543562")
        self.assertEqual(
            get.call_args.args[0], "https://api.tvmaze.com/shows/68193"
        )

    def test_missing_imdb_id_is_reported(self) -> None:
        for payload in ({}, {"externals": {}}, {"externals": {"imdb": None}}):
            with self.subTest(payload=payload), patch.object(
                tvmaze.requests, "get", return_value=FakeResponse(payload)
            ):
                with self.assertRaisesRegex(tvmaze.TVMazeError, "no IMDb ID"):
                    tvmaze.fetch_imdb_id(68193)

    def test_invalid_imdb_id_is_reported(self) -> None:
        for imdb_id in ("not-an-imdb-id", "tt123", ""):
            with self.subTest(imdb_id=imdb_id), patch.object(
                tvmaze.requests,
                "get",
                return_value=FakeResponse({"externals": {"imdb": imdb_id}}),
            ):
                with self.assertRaisesRegex(tvmaze.TVMazeError, "invalid IMDb ID"):
                    tvmaze.fetch_imdb_id(68193)


if __name__ == "__main__":
    unittest.main()
