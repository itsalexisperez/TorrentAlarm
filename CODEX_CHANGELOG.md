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

## Fase 2 — configuración multi-serie

- Fecha/hora UTC: 2026-08-27T05:17:20Z
- Objetivo: eliminar la serie única hardcodeada del motor programado y procesar todas las series habilitadas desde configuración.
- Archivos creados/modificados: `shows.py`, `shows.json`, `alarm_once.py`, `tvmaze.py`, `state.py`, `state.json`, `test_shows.py`, `test_state.py`.
- Decisiones técnicas: `shows.json` usa registros simples `{show_id, name, season, enabled}`; `shows.py` valida tipos, valores positivos y IDs únicos; `alarm_once.py` procesa cada show de forma independiente, resuelve IMDb una vez por serie con episodios pendientes y reutiliza la ventana de 12 horas basada exclusivamente en `airstamp`.
- Compatibilidad: `watcher.py` no fue modificado; el workflow mantiene una única llamada a `alarm_once.py`.
- Comandos relevantes: `.venv/bin/python -m unittest discover -v`; `.venv/bin/python -m compileall -q .`; `git diff --check`; escaneo estático de secretos, magnets, enlaces de descarga y días hardcodeados.
- Tests y resultados: `53` tests verdes; no hubo llamadas reales a TVMaze, EZTV o Telegram.
- Commits creados: pendiente de crear en esta fase.
- Runs de GitHub Actions verificados: pendiente del despliegue.
- Problemas encontrados y resolución: los tests heredados esperaban el estado plano; se actualizaron al esquema versionado sin perder la cobertura de deduplicación y fallo de Telegram.

## Fase 3 — migración de estado y fin automático de temporada

- Fecha/hora UTC: 2026-08-27T05:18:00Z
- Objetivo: preservar el historial real, hacer idempotente la migración y detener consultas EZTV cuando una temporada terminó con evidencia temporal suficiente.
- Archivos creados/modificados: `state.py`, `state.json`, `alarm_once.py`, `test_state.py`.
- Esquema final: `state.shows[show_id]` contiene `season`, `completed` y `notified`; el formato anterior por show ID se normaliza durante la carga y se persiste atómicamente en la misma ejecución.
- Decisiones técnicas: `shows.json` aporta las temporadas autoritativas durante la migración; una temporada solo completa si todos sus episodios conocidos tienen `airstamp` válido y pasado, el último supera 12 horas y no existe episodio activo. TVMaze sigue consultándose para detectar cambios de calendario; una serie completada omite IMDb/EZTV.
- Invariantes verificadas: S01E06 y S01E07 siguen verdaderas después de migrar; Telegram se marca solo después de una respuesta exitosa; un fallo deja el episodio pendiente; completion es independiente por serie.
- Comandos relevantes: `.venv/bin/python -m unittest discover -v`; `git diff --check`.
- Tests y resultados: `55` tests verdes; migración automática e idempotente, futuro `<12h`, `+12h`, serie completada y múltiples series cubiertos.
- Commits creados: pendiente de crear en esta fase.
- Runs de GitHub Actions verificados: pendiente del despliegue.
- Problemas encontrados y resolución: el esquema anterior no contenía temporada, por lo que el runtime pasa el mapa autoritativo desde `shows.json`; las lecturas independientes conservan compatibilidad con temporada 1 para no romper herramientas antiguas.

## Fase 4 — CLI para administrar series

- Fecha/hora UTC: 2026-08-27T05:19:06Z
- Objetivo: administrar `shows.json` sin editar código Python, secretos ni estado histórico.
- Archivos creados/modificados: `manage_shows.py`, `tvmaze.py`, `test_manage_shows.py`, `test_tvmaze.py`, `USAGE.md`.
- Decisiones técnicas: `list`, `add`, `disable` y `enable`; `add` busca y resuelve el nombre canónico en TVMaze, exige `--show-id` si hay ambigüedad, valida la temporada por episodios y escribe configuración atómicamente. No se implementó `remove` para evitar una política accidental de borrado histórico.
- Comandos relevantes: `.venv/bin/python -m unittest discover -v`; `git diff --check`.
- Tests y resultados: `57` tests verdes, incluyendo add duplicado, nombre ambiguo, temporada inexistente, configuración inválida, toggle y conservación de `state.json`.
- Commits creados: pendiente de crear en esta fase.
- Runs de GitHub Actions verificados: pendiente del despliegue.
- Problemas encontrados y resolución: el documento de control Telegram se reservó para la fase 7 según el orden requerido.
