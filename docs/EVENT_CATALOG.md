# Event Catalog (fase 1)

Se introdujo un catálogo mínimo en `core/event_catalog.py` para normalizar y validar eventos sin romper compatibilidad.

## Qué usar

- `EventType`: enum oficial de tipos de evento.
- `EVENT_SCHEMAS`: validaciones mínimas por `required_keys`.
- `make_event(...)`: helper para crear eventos aceptando `EventType` o `str`.

## Compatibilidad

- En esta fase se permiten **strings legacy**.
- Si llega un evento no registrado en el catálogo, se loggea `WARNING` con `event_type` y `trace_id`.
- Si faltan keys requeridas del payload, se loggea `WARNING` y el evento se marca inválido.

## Límite anti-cascada

- `EventBus` aplica presupuesto por `trace_id/request_id`.
- Configurable por env: `TRETA_MAX_EVENTS_PER_CYCLE`.
- Si se excede, se corta la publicación y se loggea `CRITICAL`.

## Cómo añadir un evento nuevo

1. Añadir miembro en `EventType`.
2. (Opcional) Añadir schema en `EVENT_SCHEMAS` con `required_keys`.
3. Usar `make_event(EventType.X, payload, ...)` en nuevos productores.
4. Si entra por HTTP/event endpoint, quedará automáticamente permitido al estar en catálogo.
