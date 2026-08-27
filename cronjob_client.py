"""Minimal, secret-safe cron-job.org REST client."""

from __future__ import annotations

from typing import Any

import requests


API_BASE_URL = "https://api.cron-job.org"
REQUEST_TIMEOUT = 20


class CronJobAPIError(RuntimeError):
    """Raised when cron-job.org rejects or cannot receive an API request."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CronJobClient:
    def __init__(
        self,
        api_key: str,
        job_id: str,
        *,
        timeout: float = REQUEST_TIMEOUT,
        session: Any = requests,
    ) -> None:
        if not api_key:
            raise ValueError("CRONJOB_API_KEY is required")
        if not job_id.isdigit() or int(job_id) <= 0:
            raise ValueError("CRONJOB_JOB_ID must be a positive integer")
        self._api_key = api_key
        self.job_id = job_id
        self.timeout = timeout
        self.session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, API_BASE_URL + path, **kwargs)
            response.raise_for_status()
        except requests.Timeout as error:
            raise CronJobAPIError("cron-job.org request timed out") from error
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            if status_code is None:
                status_code = getattr(response, "status_code", None)
            raise CronJobAPIError(
                f"cron-job.org request failed (HTTP {status_code or 'error'})", status_code
            ) from error
        except requests.RequestException as error:
            raise CronJobAPIError("cron-job.org request failed") from error
        return response

    def patch_job(self, job_delta: dict[str, object]) -> None:
        self._request("PATCH", f"/jobs/{self.job_id}", json={"job": job_delta})

    def get_job(self) -> dict[str, Any]:
        response = self._request("GET", f"/jobs/{self.job_id}")
        try:
            payload = response.json()
        except ValueError as error:
            raise CronJobAPIError("cron-job.org returned invalid JSON") from error
        details = payload.get("jobDetails") if isinstance(payload, dict) else None
        if not isinstance(details, dict):
            raise CronJobAPIError("cron-job.org returned an invalid job response")
        # Keep preflight callers away from extendedData, which may contain
        # private request headers or body data unrelated to scheduling.
        return {
            key: details.get(key)
            for key in ("jobId", "title", "enabled", "nextExecution", "schedule", "lastStatus")
        }
