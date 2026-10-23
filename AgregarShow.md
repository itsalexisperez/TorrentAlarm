Quiero añadir una nueva serie a TorrentAlarm.

## Serie a añadir

* Nombre: `NOMBRE_DE_LA_SERIE`
* Temporada: `NUMERO_DE_TEMPORADA`

## Proyecto

`/home/alexisperez/Documents/codex-proyectos/TorrentAlarm/`

TorrentAlarm ya está en producción y soporta múltiples series mediante `shows.json` y `manage_shows.py`.

Haz todo el proceso de forma autónoma.

### 1. Preparación

* Comprueba que estás en `main`.
* Ejecuta `git fetch origin`.
* Comprueba que el working tree esté limpio.
* Si `main` está detrás de `origin/main`, actualiza únicamente con `git pull --ff-only`.
* Si existen cambios locales no relacionados, DETENTE y explícame cuáles son.

### 2. Añadir la serie

Usa la interfaz existente de `manage_shows.py`.

Intenta primero:

```bash
python manage_shows.py add "NOMBRE_DE_LA_SERIE" --season NUMERO_DE_TEMPORADA
```

No modifiques manualmente `shows.json` salvo que exista un fallo real de la herramienta que deba corregirse.

Si TVMaze devuelve resultados ambiguos:

* investiga cuál corresponde realmente a la serie indicada;
* muéstrame la decisión en el informe final;
* usa `--show-id` con el ID correcto;
* no elijas silenciosamente una serie dudosa.

Si la serie o temporada no existe en TVMaze, DETENTE sin hacer commit.

Si la misma serie y temporada ya están configuradas, no la dupliques; indícalo y termina sin cambios.

### 3. Seguridad

No:

* modifiques `alarm_once.py` ni la lógica de producción si no es necesario;
* modifiques `state.json` manualmente;
* marques episodios como notificados;
* envíes Telegram de prueba;
* muestres secrets;
* modifiques cron-job.org;
* añadas `schedule:` a GitHub Actions;
* uses `gh workflow run`;
* uses force-push.

Añadir una serie debería ser principalmente un cambio de configuración.

### 4. Validación

Después de añadirla:

* comprueba que `shows.json` contiene el `show_id`, nombre, temporada y `enabled: true` correctos;
* ejecuta todos los tests;
* no continúes si alguno falla;
* ejecuta `python manage_shows.py list`;
* comprueba que la nueva serie aparece correctamente;
* revisa `git diff`.

### 5. Publicación

Si todo está correcto:

```bash
git add shows.json
```

No añadas otros archivos accidentalmente.

Haz un commit con un mensaje como:

```text
Add NOMBRE_DE_LA_SERIE season NUMERO_DE_TEMPORADA
```

Haz push normal a `origin/main`.

### 6. Verificación en producción

NO ejecutes manualmente GitHub Actions.

Espera al siguiente disparo natural de cron-job.org.

Comprueba la primera ejecución posterior al push y confirma:

* ID del run;
* SHA ejecutado;
* resultado `success` o error;
* que la nueva serie fue cargada desde `shows.json`;
* que TVMaze pudo procesarla;
* si tenía o no un episodio activo;
* si EZTV fue consultado, cuando corresponda;
* si hubo Telegram real, únicamente si naturalmente existía un episodio activo con release;
* si `state.json` cambió;
* si hubo commit automático de estado.

No provoques ninguna notificación falsa.

Si durante la ejecución aparece un release real y Telegram se envía naturalmente, comprueba también la siguiente ejecución para confirmar que no se duplica.

### 7. Estado local

Si GitHub Actions creó un commit automático de `state.json`, sincroniza después la copia local mediante:

```bash
git pull --ff-only
```

### 8. Informe final

Al terminar dime:

* serie añadida;
* temporada;
* TVMaze show_id;
* cambio realizado en `shows.json`;
* total de tests y resultado;
* commit creado;
* resultado del push;
* run natural de producción verificado;
* resultado de TVMaze/EZTV;
* si hubo Telegram;
* si cambió `state.json`;
* `git status --short --branch` final.

No realices ninguna otra refactorización o mejora no necesaria para añadir esta serie.
