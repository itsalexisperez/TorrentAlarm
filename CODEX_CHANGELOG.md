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

## Fase 5 — suite completa, invariantes y documentación

- Fecha/hora UTC: 2026-08-27T05:19:44Z
- Objetivo: validar la refactorización completa y dejar documentada la operación segura.
- Archivos creados/modificados: `USAGE.md`, `test_shows.py`, `test_manage_shows.py`, `test_state.py`, `test_tvmaze.py` y módulos del runtime ya descritos en fases anteriores.
- Decisiones técnicas: mantener el workflow en `workflow_dispatch`, conservar `concurrency` y limitar el commit automático a `state.json`; no se añadieron llamadas reales a integraciones en la suite.
- Invariantes inspeccionadas: ventana de 12 horas; deduplicación; marca posterior a Telegram exitoso; pendiente tras fallo; aislamiento entre series; omisión EZTV para completion; EZTV `eztv.wf` primario y `eztv.tf` solo ante error técnico; respuesta válida sin episodio no activa fallback; ausencia de uso productivo de EXTTO, magnets, URLs de descarga o hashes.
- Comandos relevantes: `.venv/bin/python -m unittest discover -v`; `.venv/bin/python -m compileall -q .`; `git diff --check`; revisión de `.github/workflows/torrent-alarm.yml`; `python manage_shows.py list`.
- Tests y resultados: `57` tests verdes con Python `3.14.6`; configuración validada y CLI lista mostró ambas series habilitadas.
- Commits creados: pendiente de crear en esta fase.
- Runs de GitHub Actions verificados: pendiente de integración; no se usó `gh workflow run`.
- Problemas encontrados y resolución: ninguno bloqueante. El paquete de instrucciones no rastreado se conserva fuera de los commits del producto.

## Fase 6 — integración, push y validación real

- Fecha/hora UTC: 2026-08-27T05:31:30Z
- Objetivo: integrar solo tras suite verde y validar dos ejecuciones naturales posteriores al merge.
- Rama y commits: `feature/multi-show-config` se publicó sin force-push; merge normal a `main` en `ce856c7`.
- Archivos verificados antes del merge: `shows.json` con The Shards `68193` temporada `1` y Ted Lasso `44458` temporada `4`, ambos habilitados; `state.json` con The Shards `S01E06=true` y `S01E07=true`.
- Tests y resultados: suite completa verde con `57` tests en Python `3.14.6`; `git diff --check` y escaneo de secretos pasaron.
- Run natural 1: ID `33042426091`, creado `2026-08-27T05:25:04Z`, SHA `ce856c7`, `success`. TVMaze/EZTV no reportaron error; The Shards omitió S01E06/S01E07 como ya notificadas; Ted Lasso fue procesada sin episodio activo reportado; Telegram no envió mensaje; `state.json` sin cambios.
- Run natural 2: ID `33042687302`, creado `2026-08-27T05:30:07Z`, SHA `ce856c7`, `success`. Repitió la deduplicación de The Shards; sin Telegram nuevo, sin cambio de `state.json` ni commit automático.
- Runs anteriores al merge: no se contaron para el criterio, aunque también fueron exitosos sobre el SHA baseline.
- Problemas encontrados y resolución: no hubo commits automáticos de estado ni conflictos; `origin/main` permaneció en `ce856c7` después de ambos runs.

## Fase 7 — diseño futuro de control Telegram (no implementado)

- Fecha/hora UTC: 2026-08-27T05:31:30Z
- Objetivo: documentar un camino futuro para `/list`, `/add`, `/disable`, `/enable` y opcionalmente `/remove` sin introducir complejidad en producción ahora.
- Archivo creado: `FUTURE_TELEGRAM_CONTROL.md`.
- Decisiones técnicas: recomendar bot/controlador separado del notifier, autorización exacta por `TELEGRAM_CHAT_ID`, parsing seguro, escritura atómica, coordinación con commits de `state.json` y workflow parametrizado; se desaconseja polling permanente dentro de GitHub Actions.
- Implementación deliberadamente omitida: no hay listener, webhook, polling ni comandos Telegram.
- Tests y resultados: la suite existente permanece verde; no se hicieron llamadas Telegram de prueba.
- Commits creados: pendiente de crear en esta fase.
- Runs de GitHub Actions verificados: los dos runs naturales de fase 6 ya fueron validados; esta fase no cambia runtime.

## Cierre y reporte final

- Fecha/hora UTC: 2026-08-27T05:42:34Z
- Objetivo: dejar el reporte compartible y confirmar el estado remoto final.
- Archivo creado: `CODEX_FINAL_REPORT.md`.
- Resultado: `main` coincide con `origin/main` en `e715493` antes del commit de cierre; los dos runs naturales posteriores al merge final fueron `success` y no generaron cambios de estado.
- Última suite local: `57` tests verdes con Python `3.14.6`; `git diff --check` verde.
- Notificaciones reales durante validación: ninguna nueva; no se enviaron Telegram de prueba.
- Nota de estado: el único elemento no rastreado es el paquete de instrucciones original `TorrentAlarm_Codex_Autonomous_Plan/`, deliberadamente conservado fuera del producto.
