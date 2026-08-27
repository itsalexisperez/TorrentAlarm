# Smart Scheduler changelog

## 2026-08-27 — Fase A

- Added pure `ACTIVE_POLL`, `NEXT_WAKE`, `HEARTBEAT`, and `DISABLED` schedule decisions.
- Added secret-safe cron-job.org PATCH client with timeout and HTTP failure handling.
- Added applied scheduler metadata to `state.json` without changing `state.shows` or notification deduplication.
- Added a one-time job-title preflight; failed preflights back off for one hour to remain below the API quota.
- Added fingerprint-based PATCH minimization and atomic state persistence after successful PATCH only.
- Added Smart Scheduler reconciliation to the existing external-trigger workflow.
- Added `scheduler-reconcile.yml` for `shows.json` changes and manual recovery; no GitHub Actions schedule was added.
- Kept the feature disabled until the required GitHub secret and variables were configured.

## 2026-08-27 — Fase B

- Confirmed GitHub configuration and verified job `8335122` is titled `TorrentAlarm`.
- Natural alarm run applied the first `NEXT_WAKE` schedule; subsequent reconciliation made no PATCH because the fingerprint was unchanged.
- Recorded `NEXT_WAKE` for 2026-09-02 12:00 UTC and observed 15 minutes with no further five-minute alarm runs.
- No test Telegram message or synthetic notification was sent.

## Safety notes

- `SMART_SCHEDULER_ENABLED` must equal `true` before any cron-job.org API call is possible.
- Missing credentials fail closed when the flag is enabled; they do not affect the legacy path while disabled.
- `NEXT_WAKE` includes remaining five-minute slots in the target hour as a conservative external-trigger recovery window.
