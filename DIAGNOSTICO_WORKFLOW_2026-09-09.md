# Diagnóstico de TorrentAlarm — 2026-09-09 UTC

## Hallazgo principal

Los runs `#354`, `#355` y `#356` fallaron en el paso `Check active episodes and notify Telegram`, todos sobre el commit `d089519`. El run `#353`, sobre el commit anterior, fue exitoso.

El log del run `#356` muestra:

```text
ERROR: Ted Lasso S04E06 | EZTV | 403 Client Error: Forbidden for url: https://extto.com/browse/?q=Ted+Lasso+S04E06
Process completed with exit code 1.
```

La secuencia real fue:

1. TVMaze entregó el episodio pendiente.
2. EZTV no devolvió un torrent exacto para `Ted Lasso S04E06`.
3. El fallback EXTTO respondió `HTTP 403` desde el runner de GitHub Actions.
4. `alarm_once.py` trató esa indisponibilidad externa como error fatal y devolvió `1`.
5. El scheduler sí terminó correctamente y mantuvo el episodio en `ACTIVE_POLL`, por lo que el sistema podía reintentarlo.

La advertencia `Node 20 is being deprecated` no causó el fallo de Python, pero indicaba que las versiones usadas de las Actions debían actualizarse.

## Correcciones aplicadas

- Las caídas de todos los proveedores de torrents se clasifican como recuperables y devuelven el código `2`.
- El episodio no se marca como notificado cuando no se pudo consultar el proveedor; permanece pendiente para la siguiente ejecución.
- El workflow transforma el código `2` en una advertencia de GitHub Actions y deja fallar solo errores no recuperables, como configuración inválida, Telegram rechazando la notificación o un fallo del scheduler.
- `actions/checkout` y `actions/setup-python` se actualizaron a las ramas compatibles con Node 24.
- Se añadió un test que reproduce el `HTTP 403` de EXTTO y verifica que el episodio siga pendiente.

## Riesgos adicionales revisados

| Riesgo | Efecto | Control actual o recomendado |
| --- | --- | --- |
| TVMaze `429`, `5xx`, timeout o JSON inválido | No se calcula la ventana del episodio | El error queda aislado y se reintenta; mantener la ventana de recuperación y observar las advertencias. |
| EZTV/EXTTO cambian API, HTML o bloquean runners | No se detecta el torrent | Dos mirrors EZTV, fallback EXTTO y nuevo estado recuperable; conviene agregar otra fuente solo después de validarla. |
| Telegram `429`, `5xx`, timeout o credenciales inválidas | El episodio no se marca, o una aceptación seguida de timeout puede causar duplicado | Solo marcar después de respuesta válida; revisar `retry_after` y usar una estrategia de idempotencia si los duplicados se vuelven frecuentes. |
| Cron-job.org no responde o rechaza el PATCH | El polling puede quedar con la programación anterior | Preflight, fingerprint, timeout y no marcar metadata como aplicada si el PATCH falla. |
| Dos ejecuciones intentan guardar estado | Push/rebase fallido o estado temporalmente atrasado | Grupo de concurrencia compartido y commit limitado a `state.json`; revisar cualquier push rechazado. |
| `shows.json` o `state.json` inválidos | La ejecución termina sin procesar series | Validación estricta, migración automática y escrituras atómicas. |
| Dependencias cambian en una instalación futura | CI puede romper sin cambio de código | Mantener versiones mayores acotadas o fijadas y ejecutar CI en cada cambio. |

## Resultado esperado

Un `403` de EXTTO ya no debe producir una cadena de runs rojos. GitHub mostrará una advertencia, el scheduler seguirá consultando durante la ventana de recuperación y el episodio solo se eliminará de la cola después de una notificación Telegram confirmada.
