# TRETA Architecture

Documento operativo para entender y modificar TRETA **sin romper el core**.

## 1) Visión general

TRETA corre como un sistema event-driven con un runtime único que integra:

1. **HTTP/API + UI estática** (`core/ipc_http.py`, `ui/`)
2. **Orquestación** (`core/app.py`, `core/dispatcher.py`, `core/control.py`)
3. **Motores de decisión/estrategia** (`core/*engine*.py`, `core/services/`)
4. **Persistencia** (SQLite + stores JSON)

El objetivo del runtime es sostener el ciclo:

`oportunidad → propuesta → plan → lanzamiento → estrategia`

## 2) Punto de entrada y runtime flow

- **Entry point:** `main.py`
- `main.py` crea `TretaApp` y ejecuta `app.run()`.
- `TretaApp` (`core/app.py`):
  - inicializa `Storage` (SQLite) + migraciones,
  - construye stores y engines,
  - levanta servidor HTTP,
  - arranca scheduler,
  - procesa eventos del bus en loop.

Flujo simplificado de runtime:

1. `main.py` inicia proceso.
2. `TretaApp` inicializa dependencias y estado.
3. `start_http_server()` expone endpoints + SPA.
4. Scheduler/HTTP generan eventos.
5. `Dispatcher` consume eventos y delega en `Control` / engines.
6. Stores persisten resultados (SQLite/JSON).

## 3) Módulos principales

### Core / Orquestación

- `core/app.py`: composición de dependencias del sistema.
- `core/dispatcher.py`: despacho de eventos.
- `core/control.py`: coordinación de acciones de dominio.
- `core/state_machine.py`: estado global del runtime.

### Motores / Engines

- Oportunidad y producto: `core/opportunity_engine.py`, `core/product_engine.py`, `core/product_builder.py`.
- Ejecución y estrategia: `core/execution_engine.py`, `core/strategy_engine.py`, `core/strategy_decision_engine.py`, `core/strategic_loop_engine.py`.
- Riesgo/autonomía/políticas: `core/risk_evaluation_engine.py`, `core/autonomy_policy_engine.py`, `core/adaptive_policy_engine.py`.
- Rendimiento: `core/performance_engine.py`, `core/launch_metrics.py`.

### Persistencia

- **SQLite**: conexión y estado runtime en `core/storage.py`, migraciones en `core/migrations/`.
- **Stores JSON** (dominio): propuestas, planes, lanzamientos, oportunidades, métricas auxiliares (`core/*store*.py`).

### UI

- HTML/CSS/JS estático en `ui/`.
- Servida por el servidor HTTP propio (`core/ipc_http.py`).
- Interacción por endpoints REST + polling.

### Docker / entorno

- `docker-compose.yml`: servicio `treta`, contenedor `treta-core`, puerto `7777:7777`.
- `Dockerfile`: imagen Python slim y arranque por `python main.py`.

## 4) Flujo de datos y eventos

- Entrada por HTTP o scheduler.
- Se publica/consume en `EventBus` (`core/bus.py`).
- `Dispatcher` ejecuta transiciones/acciones.
- `Control` y engines aplican reglas.
- Persistencia en stores (SQLite/JSON).
- UI consulta estado por endpoints y refresco periódico.

## 5) Dónde tocar y dónde NO tocar

### Sí tocar (preferente)

- Cambios puntuales en un engine/store específico.
- Ajustes de endpoints en `core/ipc_http.py` sin alterar contratos existentes.
- UI incremental en `ui/` manteniendo estructura actual.
- Documentación y reglas IA.

### Evitar tocar sin análisis fuerte

- Inicialización global de `TretaApp` (`core/app.py`).
- Contratos de eventos compartidos (`core/events.py`, `core/event_catalog.py`).
- Migraciones SQLite ya aplicadas (`core/migrations/00x_*.py`).
- Reglas de integridad de dominio (`core/domain/`).

## 6) Guardrails de cambio

Antes de editar, revisar impacto en:

1. Backend/orquestación
2. Eventos
3. Persistencia (SQLite + JSON)
4. UI/polling

Si el cambio no requiere modificar una capa, **no tocarla**.
