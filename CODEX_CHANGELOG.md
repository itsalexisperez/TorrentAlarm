# CODEX Change Log

## Fase 1 — baseline, inventario y rama segura

- Fecha/hora UTC: 2026-08-27T05:08:25Z
- Objetivo: capturar el estado de producción, comprobar la suite existente y aislar el trabajo en una rama.
- `BASELINE_SHA`: `6572e83f3635ffe3a4dba5f1e7febaa02de770d7`
- Estado inicial: `main` coincidía con `origin/main` (`0` commits por delante, `0` por detrás); había únicamente un paquete de instrucciones no rastreado, conservado sin cambios.
- Rama creada: `feature/multi-show-config`.
- Archivos relevantes inspeccionados: `alarm_once.py`, `state.py`, `state.json`, `tvmaze.py`, `check_eztv.py`, `telegram_notify.py`, `watcher.py`, `.github/workflows/torrent-alarm.yml`, `requirements.txt` y tests existentes.
- Estado confirmado antes de modificar: `state.json` conserva `68193/S01E06=true` y `68193/S01E07=true`.
- Decisiones técnicas: mantener `watcher.py` como herramienta local/manual; preservar `workflow_dispatch`, `concurrency`, EZTV primario/fallback y la persistencia de estado existente.
- Comandos relevantes: `git fetch origin main`; `git rev-list --left-right --count main...origin/main`; `.venv/bin/python --version`; `.venv/bin/python -m unittest discover -v`.
- Tests y resultados: Python `3.14.6`; suite baseline verde, `39` tests ejecutados, `OK`.
- Commits creados: ninguno todavía.
- Runs de GitHub Actions verificados: no aplica en baseline; aún no hubo despliegue.
- Problemas encontrados y resolución: no hubo fallos bloqueantes; el paquete de instrucciones no rastreado quedó fuera del alcance de cambios.

