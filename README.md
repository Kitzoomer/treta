# TRETA

TRETA es un **sistema operativo de decisiones** (no un chatbot simple) con ciclo completo:
**oportunidad → propuesta → plan → lanzamiento → estrategia**, con persistencia local, motores de decisión y automatización controlada.

## Stack y ejecución local

- Backend: Python (servidor HTTP propio, sin framework pesado).
- Arquitectura: event-driven in-process.
- Persistencia: SQLite (`data/memory/treta.sqlite`) + stores JSON de dominio.
- UI: SPA simple (`ui/index.html` + `ui/app.js`) con polling periódico.
- Runtime local esperado: Windows host + WSL2 Ubuntu + Docker Compose.
- Servicio principal: `treta` (contenedor `treta-core`).
- URL local: <http://localhost:7777>

## Arranque rápido

```bash
docker compose up --build
```

Checks mínimos:

```bash
curl http://localhost:7777/health
curl http://localhost:7777/ready
```

## Flujo recomendado tras merge

```bash
git pull
docker compose down
docker compose up --build
```

## Documentación clave

- Arquitectura y boundaries: `docs/ARCHITECTURE.md`
- Workflow de desarrollo seguro: `docs/dev-workflow.md`
- Catálogo de eventos: `docs/EVENT_CATALOG.md`
- Reglas para asistentes IA: `.cursorrules` y `AGENTS.md`

## Seguridad y configuración

- Usa `.env` local (no versionado) basado en `.env.example`.
- No hardcodear claves/API tokens.
- Mantener compatibilidad con Docker/WSL2 y evitar sobreingeniería.
