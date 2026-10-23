# FASE 2 — Tests, deploy y verificación real

## Tests offline obligatorios

### Config
- campo omitido => 0
- 0 válido
- -660 válido
- positivo válido
- string inválido
- float inválido
- bool inválido si corresponde
- fuera del límite elegido => inválido

### Helper
Con TVMaze `2026-09-02T12:00:00Z`:
- offset 0 => 12:00 UTC
- offset -660 => 01:00 UTC
- offset +60 => 13:00 UTC

### alarm_once
Para una serie con -660:
- 00:59:59 UTC => inactivo
- 01:00 UTC => activo
- dentro de +12h => activo
- 13:00 UTC exacto => inactivo

Asegurar que default 0 conserva comportamiento existente.

### Smart Scheduler
Con Ted Lasso:
- NEXT_WAKE usa 01:00 UTC, no 12:00 UTC
- ACTIVE_POLL empieza a 01:00 UTC
- expiración se calcula desde effective_airstamp
- fingerprint cambia al cambiar `release_offset_minutes`
- reconciliación posterior con mismo offset => 0 PATCH
- múltiples shows con offsets distintos funcionan

### Completion
- final de temporada usa effective_airstamp + 12h
- no completed antes del límite
- completed en/después del límite según semántica existente

### Deduplicación
- cambiar offset NO elimina ni reenvía episodios ya notificados
- The Shards S01E06/S01E07 permanecen intactos

### CLI
- add con `--release-offset-minutes`
- modificación de offset si implementaste comando
- list muestra el offset o al menos no lo pierde

No hacer llamadas reales a TVMaze/EZTV/Telegram en tests.

Ejecutar suite COMPLETA. No continuar si falla.

## Git y deploy
1. Revisar diff.
2. Confirmar que no hay secrets.
3. Confirmar que no apareció GitHub `schedule:`.
4. Commit(s) lógicos.
5. Merge/push a main.
6. No force-push.

## Reconciliación real
Preferencia:
- dejar que `scheduler-reconcile.yml` provocado por el cambio de `shows.json` haga el PATCH;
- no editar cron-job.org manualmente.

Inspeccionar:
- run ID;
- conclusion;
- PATCH count;
- fingerprint;
- cron-job.org nextExecution.

## Resultado esperado para Ted Lasso
Si TVMaze sigue reportando:
`2026-09-02T12:00:00Z`

con `release_offset_minutes=-660`:

esperado:
`nextExecution` alrededor de `2026-09-02T01:00:00Z`

No aceptar 12:00 UTC como resultado final.

## Verificación cron-job.org
Consultar API sin imprimir secretos ni headers sensibles.

Registrar:
- jobId
- title verificado
- enabled
- nextExecution
- schedule
- expiresAt si aplica

## Producción
No enviar Telegram de prueba.

Si no hay episodio activo:
- no debe aparecer polling cada 5 min;
- NEXT_WAKE debe quedar adelantado.

Si naturalmente aparece un episodio/release durante la validación:
- permitir flujo real;
- comprobar deduplicación en siguiente run.

## State
Si GitHub Actions crea commit automático de state:
- sincronizar local con `git pull --ff-only`.

## Reporte final
Crear `RELEASE_OFFSET_FINAL_REPORT.md` con:
- BASELINE_SHA
- SHA final
- archivos modificados/creados
- tests total
- esquema final de shows.json
- offset Ted Lasso
- effective next wake calculado
- run de scheduler-reconcile
- PATCH real
- nextExecution real de cron-job.org
- evidencia de que The Shards mantiene offset 0
- S01E06/S01E07 preservados
- Telegram de prueba: NO
- git status final
- rollback simple:
  - poner Ted Lasso offset en 0
  - commit/push
  - dejar scheduler-reconcile reprogramar

Resultado final:
`RELEASE_OFFSET_OPERATIONAL`
o, si falla:
`RELEASE_OFFSET_NOT_DEPLOYED`
