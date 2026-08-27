# Release offset

## 2026-08-27

- Añadido `release_offset_minutes` opcional por serie en `shows.json`.
- El valor por defecto es `0`; se aceptan enteros entre `-10080` y `10080` (±7 días), incluidos valores negativos y positivos.
- Centralizado el cálculo `effective_airstamp = tvmaze_airstamp + offset` en `temporal.py`.
- Aplicado el offset a la ventana de `alarm_once.py`, ACTIVE_POLL, NEXT_WAKE, expiración del scheduler y completion de temporada.
- Añadidos `--release-offset-minutes` a `manage_shows.py add` y `set-offset` para modificar una serie sin tocar `state.json`.
- Configuración de producción: The Shards usa `0`; Ted Lasso temporada 4 usa `-660`.
- No se modificaron contratos EZTV, Telegram, deduplicación, `watcher.py`, secrets, workflow dispatch ni el scheduler externo.
