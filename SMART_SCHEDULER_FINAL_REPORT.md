# SMART_SCHEDULER_FINAL_REPORT

## Estado

- Resultado: `SMART_SCHEDULER_NOT_ACTIVATED`
- BASELINE_SHA: `bd25ada0d78e812e32c1e766c72391960d774d0a`
- SHA final: se registrará en el handoff tras la integración de Fase A
- Tests: 74/74 passing

## Antes

- Runs teóricos/día: 288 (cada 5 minutos)
- Evidencia: los 20 runs recientes consultados fueron `workflow_dispatch` exitosos y espaciados aproximadamente 5 minutos.

## Fase A desplegada

- Modos: `ACTIVE_POLL`, `NEXT_WAKE`, `HEARTBEAT`, `DISABLED`.
- `state.json`: conserva `state.shows`; metadata aplicada queda en `state.scheduler`.
- Workflow existente: mantiene solo `workflow_dispatch`; no se añadió GitHub `schedule:`.
- Reconcile adicional: cambios de `shows.json` y `workflow_dispatch`, con la misma concurrencia y sin Telegram/EZTV.
- Tests offline: decisiones, límites UTC/offset, expiración, fingerprint, fallos API, estado atómico y flag apagado.

## API cron-job.org

- PATCH endpoint: `/jobs/<jobId>` con delta de `job.schedule`/`job.enabled`.
- PATCH reales: 0; activación no autorizada por credenciales ausentes.
- Requests/día estimadas durante operación: 0 cuando el fingerprint no cambia; como máximo una por transición de schedule, muy por debajo de 100/día.
- `CRONJOB_API_KEY`, `CRONJOB_JOB_ID` y `SMART_SCHEDULER_ENABLED` no están configurados en GitHub al momento del checkpoint.

## Producción

- `The Shards` (68193, S01): preservados S01E06/S01E07 notificados.
- `Ted Lasso` (44458, S04): configuración preservada.
- Telegram: no se envió mensaje de prueba ni se activó el scheduler.
- Modo/nextExecution/PATCH real: no disponibles porque la activación quedó detenida de forma segura.

## Fail-safes y rollback

- `ACTIVE_POLL` expira 15 minutos después del máximo de las ventanas activas.
- `NEXT_WAKE` usa UTC, fecha exacta y slots de 5 minutos restantes en la hora objetivo como recuperación conservadora.
- Un fallo de TVMaze o PATCH no marca metadata como aplicada.
- Rollback: establecer `SMART_SCHEDULER_ENABLED=false`; si hiciera falta, restaurar manualmente el job a cada 5 minutos mediante PATCH.

## Git

- Rama de trabajo: `feature/smart-scheduler`.
- Cambios no relacionados preexistentes preservados: `AgregarShow.md` y `TorrentAlarm_Smart_Scheduler_Codex_Plan/`.
