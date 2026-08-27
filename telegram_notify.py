"""Send Telegram notifications using environment-provided credentials."""

from __future__ import annotations

import os

import requests


TELEGRAM_API_URL = "https://api.telegram.org"
REQUEST_TIMEOUT = 20


class TelegramNotificationError(RuntimeError):
    """Raised when a Telegram notification cannot be delivered."""


def _required_environment_value(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise TelegramNotificationError(f"missing required environment variable: {name}")
    return value


def send_message(message: str) -> dict[str, object]:
    """Send ``message`` to the configured Telegram chat and return Telegram's response."""
    if not message:
        raise ValueError("message must not be empty")

    token = _required_environment_value("TELEGRAM_BOT_TOKEN")
    chat_id = _required_environment_value("TELEGRAM_CHAT_ID")
    url = f"{TELEGRAM_API_URL}/bot{token}/sendMessage"

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise TelegramNotificationError("Telegram request timed out") from error
    except requests.HTTPError as error:
        raise TelegramNotificationError(
            f"Telegram returned HTTP {response.status_code}"
        ) from error
    except requests.RequestException as error:
        raise TelegramNotificationError("Telegram request failed") from error

    try:
        payload = response.json()
    except ValueError as error:
        raise TelegramNotificationError("Telegram returned invalid JSON") from error

    if not isinstance(payload, dict) or payload.get("ok") is not True:
        description = payload.get("description") if isinstance(payload, dict) else None
        if description:
            raise TelegramNotificationError(f"Telegram rejected the message: {description}")
        raise TelegramNotificationError("Telegram rejected the message")

    return payload
