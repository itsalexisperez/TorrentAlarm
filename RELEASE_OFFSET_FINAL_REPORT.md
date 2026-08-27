# RELEASE_OFFSET_FINAL_REPORT

## Resultado

`RELEASE_OFFSET_OPERATIONAL`

- BASELINE_SHA: `44e2394762e79ddde5692b62ec01ae5c98eef147`
- Implementación: `91888230799a108be41a641f31ae2da15da06093`
- SHA final desplegado/verificado: `e28952b47c505a84fccf910760b2d0ebfcc5f038`
- Rama: `feature/release-offset`, integrada en `main` mediante fast-forward y push normal.
- Estado Git final: `main` sincronizado con `origin/main`; solo permanecen los archivos no rastreados preexistentes `AgregarShow.md` y `TorrentAlarm_Release_Offset_Codex_Plan/`.

## Implementación

- `release_offset_minutes` opcional, entero, default `0`, límite `±10080` minutos (±7 días); strings, floats, bools y valores fuera de rango se rechazan.
- Helper único: `temporal.effective_airstamp` conserva timezone-awareness y aplica `timedelta(minutes=release_offset_minutes)`.
- `alarm_once.py`: ventana activa y completion usan el timestamp efectivo.
- `smart_scheduler.py`: ACTIVE_POLL, NEXT_WAKE, expiración, próximo episodio y fingerprint usan/contemplan el offset.
- `manage_shows.py`: soporta `add --release-offset-minutes` y `set-offset --minutes`; no toca `state.json`.
- No se modificaron EZTV, Telegram, deduplicación, `watcher.py`, secrets ni workflows `workflow_dispatch`; no apareció GitHub Actions `schedule:`.

## Configuración desplegada

- The Shards `68193`, temporada 1: `release_offset_minutes=0`.
- Ted Lasso `44458`, temporada 4: `release_offset_minutes=-660`.
- TVMaze conserva el episodio, season/episode y `airstamp` original.
- Para `2026-09-02T12:00:00Z`, el effective airstamp y NEXT_WAKE son `2026-09-02T01:00:00Z`.

## Tests y reconciliación

- Suite completa local: `88/88` passing.
- CI run: `33114699782`, `success`.
- Scheduler reconcile run: `33114699818`, `success`; job `98666230388`, todos los pasos verdes.
- Log del reconcile: `SCHEDULE_PATCHED: NEXT_WAKE | next known episode at 2026-09-02T01:00:00+00:00`.
- PATCH real: `1`, generado por `scheduler-reconcile.yml`; la reconciliación siguiente con el mismo fingerprint queda cubierta por tests con `0 PATCH`.
- Job verificado por el preflight persistido: jobId `8335122`, título `TorrentAlarm`, `title_verified=true`.
- Target aplicado: enabled `true`, timezone `UTC`, hour `1`, day `2`, month `9`, slots de 5 minutos, `expiresAt=20260902131500`.
- `state.json` remoto conserva The Shards `S01E06` y `S01E07` como notificados.
- La API key no existe en el entorno local; por eso no se ejecutó un GET adicional independiente ni se imprimieron headers/secretos. El workflow sí completó el PATCH real y persistió el target efectivo. `nextExecution` esperado por la schedule aplicada: alrededor de `2026-09-02T01:00:00Z`; no se acepta el antiguo `12:00 UTC`.

## Seguridad y rollback

- Telegram de prueba: `NO`.
- No se tocaron magnets, URLs, hashes ni `state.json` manualmente.
- Rollback simple: establecer el offset de Ted Lasso en `0`, hacer commit/push y dejar que `scheduler-reconcile.yml` reprograme cron-job.org.
