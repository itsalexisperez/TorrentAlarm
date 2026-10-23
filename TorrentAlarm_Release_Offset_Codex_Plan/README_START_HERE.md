# TorrentAlarm — Release Offset para Codex

Objetivo: añadir un ajuste horario opcional por serie para que TorrentAlarm no dependa ciegamente del `airstamp` de TVMaze cuando una plataforma publica episodios antes de esa hora.

Caso concreto:
- Ted Lasso
- TVMaze show_id: 44458
- temporada: 4
- `release_offset_minutes = -660`

The Shards debe conservar comportamiento actual con offset 0.

## Uso
1. Extrae este ZIP.
2. Abre Codex en `/home/alexisperez/Documents/codex-proyectos/TorrentAlarm/`.
3. Dale acceso a esta carpeta.
4. Pega únicamente `00_MASTER_ORCHESTRATOR.md`.
5. Codex ejecutará el plan completo solo.

Al terminar, comparte con ChatGPT `RELEASE_OFFSET_FINAL_REPORT.md`.
