# SMART_SCHEDULER_SETUP_REQUIRED

Fase A quedó desplegada con el feature apagado porque la cuenta de GitHub no tiene todavía la configuración requerida. No se activó ningún cambio en cron-job.org.

Configurar una sola vez, sin pegar secretos en ChatGPT ni en archivos del repositorio:

1. En cron-job.org → Settings, crear una API key.
2. Obtener el `jobId` del job cuyo título es `TorrentAlarm` mediante la API o la consola.
3. Guardar en GitHub:

```bash
read -rsp 'CRONJOB_API_KEY: ' CRONJOB_API_KEY; echo
export CRONJOB_API_KEY
printf '%s' "$CRONJOB_API_KEY" | gh secret set CRONJOB_API_KEY
gh variable set CRONJOB_JOB_ID --body "JOB_ID_DE_TorrentAlarm"
gh variable set SMART_SCHEDULER_ENABLED --body "true"
```

Verificar únicamente nombres, nunca valores:

```bash
gh secret list
gh variable list
```

Después de configurar los tres valores, la siguiente ejecución natural de `TorrentAlarm` hará el preflight/reconcile; no es necesario cambiar manualmente el cron de 5 minutos.

Rollback:

```bash
gh variable set SMART_SCHEDULER_ENABLED --body "false"
```

Con el flag en `false`, la ejecución vuelve al polling externo de 5 minutos y no llama a la API de cron-job.org.
