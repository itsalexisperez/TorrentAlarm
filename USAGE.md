# Uso de TorrentAlarm

## Arquitectura

El workflow `workflow_dispatch` ejecuta una sola vez `alarm_once.py`. En cada ejecución, el motor carga `shows.json`, consulta TVMaze para cada serie habilitada y filtra la temporada configurada usando `airstamp` y una ventana activa de 12 horas. Después consulta EZTV y envía Telegram solo para episodios exactos aún no notificados. `watcher.py` queda reservado para uso local/manual.

El scheduler externo (cron-job.org) es quien dispara el workflow cada cinco minutos. No se programa por martes, miércoles ni otro día de la semana: TVMaze es la fuente de verdad temporal.

## Configuración

`shows.json` es versionado y editable:

```json
{
  "shows": [
    {
      "show_id": 68193,
      "name": "The Shards",
      "season": 1,
      "enabled": true,
      "release_offset_minutes": 0
    },
    {
      "show_id": 44458,
      "name": "Ted Lasso",
      "season": 4,
      "enabled": true,
      "release_offset_minutes": -660
    }
  ]
}
```

Cada `show_id` debe ser un entero positivo único; `name` no puede estar vacío; `season` debe ser positiva y `enabled` debe ser booleano. `release_offset_minutes` es opcional, por defecto `0`, debe ser un entero entre `-10080` y `10080` (±7 días). Un valor negativo adelanta el inicio de vigilancia respecto de TVMaze; uno positivo lo retrasa. No modifica el `airstamp` original de TVMaze: solo corrige la ventana efectiva de vigilancia.

## Estado persistente

`state.json` se escribe de forma atómica y tiene un historial independiente por show:

```json
{
  "shows": {
    "68193": {
      "season": 1,
      "completed": false,
      "notified": {
        "S01E06": true,
        "S01E07": true
      }
    }
  }
}
```

El formato legado `{ "show_id": { "SxxEyy": true } }` se migra automáticamente durante una ejecución normal. Los episodios marcados se conservan y la escritura de estado solo ocurre después de una notificación Telegram aceptada.

Una temporada pasa a `completed: true` cuando TVMaze muestra al menos un episodio de la temporada, todos los episodios conocidos tienen `airstamp` válido y pasado, el último terminó hace al menos 12 horas y no queda un episodio activo. La serie sigue pudiendo consultarse en TVMaze para detectar cambios de calendario, pero no se consulta EZTV mientras esté completada.

## CLI de series

```bash
python manage_shows.py list
python manage_shows.py add "Ted Lasso" --season 4
python manage_shows.py add "Ted Lasso" --season 4 --release-offset-minutes -660
python manage_shows.py set-offset "Ted Lasso" --minutes -660
python manage_shows.py add "Nombre ambiguo" --season 1 --show-id 12345
python manage_shows.py disable "The Shards"
python manage_shows.py enable "The Shards"
```

`add` busca el nombre en TVMaze, conserva el nombre canónico, valida que la temporada exista y no modifica `state.json`, secretos ni Telegram. Si hay varios resultados se debe usar `--show-id`. Deshabilitar y reactivar una serie conserva su historial, por lo que no repite episodios ya notificados. Cambiar el offset tampoco borra ni reenvía episodios ya notificados; el cambio de `shows.json` provoca la reconciliación del scheduler.

## Recuperación y mantenimiento

- Un error de TVMaze, EZTV o Telegram queda aislado a la serie o episodio afectado y la siguiente ejecución puede reintentarlo.
- Un fallo de Telegram no marca el episodio como enviado.
- El workflow conserva `concurrency` para evitar ejecuciones solapadas y solo permite que el commit automático agregue `state.json`.
- Para añadir una serie nueva, usar `manage_shows.py add`, revisar el diff de `shows.json` y publicar ese cambio normalmente; no crear otro workflow ni hardcodear días.
