# FASE 1 — Implementación genérica

## 1. Baseline
- `git fetch origin`
- comprobar `main`
- `git pull --ff-only` si corresponde y working tree está limpio
- guardar BASELINE_SHA
- ejecutar suite actual
- leer `shows.py`, `shows.json`, `manage_shows.py`, `alarm_once.py`, `smart_scheduler.py`, `state.py`, lógica de completion, workflows y tests
- crear rama `feature/release-offset`

## 2. Esquema shows.json
Añadir soporte opcional:

```json
{
  "show_id": 44458,
  "name": "Ted Lasso",
  "season": 4,
  "enabled": true,
  "release_offset_minutes": -660
}
```

Para The Shards dejar el campo omitido o `0`; ambos deben ser equivalentes.

## 3. Validación
En configuración:
- `release_offset_minutes` entero;
- default 0;
- aceptar negativos y positivos;
- rechazar tipos inválidos;
- usar un límite razonable para detectar errores, por ejemplo ±7 días, y documentarlo.

## 4. Helper temporal único
Evitar duplicar aritmética. Crear o reutilizar una función clara, por ejemplo:

```python
effective_airstamp(airstamp, release_offset_minutes)
```

Debe:
- conservar timezone-awareness;
- devolver `airstamp + timedelta(minutes=offset)`;
- ser fácilmente testeable.

Preferir una única fuente de verdad usada por alarm_once y Smart Scheduler.

## 5. alarm_once.py
Para cada serie:
- obtener airstamp TVMaze original;
- calcular `effective_airstamp`;
- episodio activo cuando:

```text
effective_airstamp <= now < effective_airstamp + 12h
```

No cambiar season/episode ni búsquedas EZTV.

## 6. Smart Scheduler
Aplicar el mismo `effective_airstamp` a:
- ACTIVE_POLL;
- NEXT_WAKE;
- expiración ACTIVE_POLL;
- próximo episodio.

Con Ted Lasso y offset -660:
- TVMaze `2026-09-02 12:00 UTC`
- target efectivo `2026-09-02 01:00 UTC`

El cambio de `shows.json` debe cambiar el fingerprint y reprogramar cron-job.org automáticamente.

## 7. Fin automático de temporada
Si completion usa el final de la ventana de 12h, usar:
`effective_airstamp + 12h`

No perder la capacidad de reabrir una temporada si TVMaze publica episodios futuros.

## 8. manage_shows.py
Extender CLI de forma compatible.

Soportar:
```bash
python manage_shows.py add "Serie" --season 2 --release-offset-minutes -660
```

Y preferiblemente:
```bash
python manage_shows.py set-offset "Ted Lasso" --minutes -660
```

o equivalente claro.

No borrar state al cambiar offset.

## 9. Configuración real
Actualizar `shows.json`:
- Ted Lasso / 44458 / season 4: `release_offset_minutes: -660`
- The Shards: offset 0.

## 10. Documentación
Actualizar `USAGE.md`:
- negativo = empezar antes de TVMaze;
- positivo = empezar después;
- default 0;
- ejemplo Ted Lasso;
- no cambia el dato original de TVMaze, solo la ventana efectiva de vigilancia.
