# PROMPT MAESTRO — implementar release_offset_minutes

Proyecto:
`/home/alexisperez/Documents/codex-proyectos/TorrentAlarm/`

TorrentAlarm ya está en producción con:
- multi-serie;
- Smart Scheduler operativo;
- cron-job.org controlado por API;
- TVMaze + EZTV + Telegram;
- ventana activa de 12 horas;
- `state.json` para deduplicación;
- The Shards y Ted Lasso configurados;
- GitHub Actions sin `schedule:` nativo.

Ejecuta de forma autónoma, EN ORDEN:
1. `01_IMPLEMENT_RELEASE_OFFSET.md`
2. `02_TEST_DEPLOY_VERIFY.md`

No me pidas prompts intermedios.

## Objetivo
Añadir soporte genérico y opcional de `release_offset_minutes` por serie en `shows.json`.

Semántica:
`effective_airstamp = tvmaze_airstamp + timedelta(minutes=release_offset_minutes)`

Default: `0`

Valor para Ted Lasso temporada 4: `-660`

The Shards: `0` o campo omitido.

## Regla crítica
El offset debe aplicarse coherentemente a TODA lógica temporal de producción que decide cuándo vigilar esa serie:
- `alarm_once.py`
- Smart Scheduler: ACTIVE_POLL, NEXT_WAKE y expiración
- fin automático de temporada si usa el final de la ventana activa

No basta con adelantar solo cron-job.org.

TVMaze sigue siendo la fuente del episodio, season/episode y `airstamp` original. El offset es una corrección configurable de disponibilidad.

## Compatibilidad
Configuraciones antiguas sin `release_offset_minutes` deben seguir funcionando como offset 0.

No cambies:
- contratos EZTV;
- Telegram;
- state dedup;
- scheduler externo/cron-job API;
- `watcher.py` salvo código temporal realmente compartido;
- GitHub Actions `workflow_dispatch`;
- secrets.

No reintroduzcas GitHub `schedule:`.

## Git
- comprobar `main` limpia/sincronizada;
- guardar BASELINE_SHA;
- crear rama `feature/release-offset`;
- commits lógicos;
- suite verde;
- merge/push normal;
- no force-push.

## Seguridad
Nunca:
- imprimir secrets;
- enviar Telegram falso;
- tocar magnets/torrent URLs/hashes;
- modificar `state.json` manualmente para fingir resultados;
- alterar cron-job.org manualmente si `scheduler-reconcile.yml` puede hacerlo.

## Registro
Crear:
- `RELEASE_OFFSET_CHANGELOG.md`
- `RELEASE_OFFSET_FINAL_REPORT.md`

## Detenerse si
- tests no quedan verdes;
- el cambio puede duplicar notificaciones ya persistidas;
- no puedes aplicar el offset de forma consistente a alarm_once y Smart Scheduler;
- la validación requeriría una notificación falsa;
- el cambio rompe la reconciliación de cron-job.org.

Empieza ahora.
