# TRETA Dev Workflow (Docker + WSL2)

Guía mínima para trabajar de forma segura y eficiente sin romper el core.

## 1) Levantar proyecto

Desde la raíz del repo:

```bash
docker compose up --build
```

Servicios esperados:

- `treta` (contenedor `treta-core`)
- app en `http://localhost:7777`

## 2) Verificación manual rápida

```bash
curl http://localhost:7777/health
curl http://localhost:7777/ready
```

Verificar también:

- Carga de UI en navegador.
- Endpoints clave del flujo oportunidad/propuesta/plan/lanzamiento.
- Que no aparezcan errores de migración o de SQLite en logs.

## 3) Validar cambios sin romper el core

Checklist por cada cambio:

1. Cambio mínimo y localizado (sin refactor global).
2. Revisión de impacto en eventos, persistencia y UI.
3. Smoke test de endpoints básicos (`/health`, `/ready`, flujo tocado).
4. Si se tocó persistencia, validar lectura/escritura y compatibilidad con datos existentes.
5. Si se tocó UI, comprobar que polling y navegación siguen operativos.

## 4) Flujo recomendado tras merge

```bash
git pull
docker compose down
docker compose up --build
```

## 5) Notas de seguridad

- Nunca commitear secretos ni `.env`.
- Usar `.env.example` como plantilla local.
- Mantener compatibilidad con Docker/WSL2.
- Evitar dependencias pesadas sin justificación técnica clara.
