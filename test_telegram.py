"""Manual smoke test for the Telegram integration."""

from telegram_notify import TelegramNotificationError, send_message


MESSAGE = "✅ TorrentAlarm: integración Telegram correcta"


def main() -> int:
    try:
        send_message(MESSAGE)
    except (TelegramNotificationError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1

    print("OK: Telegram notification sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
