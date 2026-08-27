# Diseño futuro: control de series por Telegram

Este documento describe una posible ampliación. No se implementan listener, webhook, polling ni comandos Telegram en la fase actual.

## Comandos propuestos

- `/list`
- `/add Ted Lasso --season 4`
- `/disable The Shards`
- `/enable The Shards`
- `/remove Nombre` (solo si se define una política clara para conservar el estado histórico)

## Aislamiento y autorización

El control debería vivir en un bot/proceso separado del notifier. Cada actualización debe aceptar únicamente mensajes cuyo `chat.id` coincida exactamente con `TELEGRAM_CHAT_ID`; cualquier otro chat se rechaza sin ejecutar parsing ni cambios. El parser debe usar argumentos estructurados, límites de longitud, validación UTF-8 y `--show-id` para resultados ambiguos, sin evaluar texto como código.

## Persistencia y concurrencia

La operación autorizada no debería escribir directamente un checkout de producción sin coordinación. Una opción segura es que el controlador genere una solicitud o dispare un workflow con parámetros; el workflow valida TVMaze, modifica `shows.json`, ejecuta tests y publica un commit revisable. Si se habilita escritura directa, debe usarse escritura atómica y bloqueo/reintento frente a commits concurrentes de `state.json`. El commit de configuración nunca debe incluir secretos ni sobrescribir el estado de notificaciones.

GitHub Actions no es apropiado para mantener un polling permanente: los jobs son efímeros y tienen límites de ejecución. Un webhook requiere un endpoint persistente y protegido. Para interacción continua, un pequeño servicio/serverless con webhook, secret de webhook, autorización por chat y una cola de cambios es más adecuado. Polling puede servir en un servicio dedicado, pero no dentro del workflow programado.

## Recomendación

Mantener separado el notifier periódico y hacer que `/add`, `/disable` y `/enable` creen una solicitud validada que dispare un workflow de configuración. `/remove`, si se añade, debe retirar solo el registro de `shows.json` y conservar explícitamente la entrada histórica de `state.json` para impedir re-notificaciones accidentales si la serie se vuelve a habilitar.
