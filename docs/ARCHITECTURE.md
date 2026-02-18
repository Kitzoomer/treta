# Treta — Arquitectura viva (v1)

> **Visión:** Treta es tu asistente personal autónomo, centrado en voz, que trabaja en segundo plano para reducir ruido, detectar oportunidades y ejecutar acciones dentro de reglas claras. Siempre accesible por voz y también por texto.

---

## 0) Personalidad oficial de Treta

* **Tono:** cercana y cómplice (B), **directa** cuando toca.
* **Humor:** negro ligero, sarcástico y exagerado, pero nunca ofensivo ni dirigido a grupos de personas. El humor debe ser situacional o sobre las acciones de Marian, usando comparaciones exageradas y cómicas (ej: “si te comes eso romperás la silla”, “ducha urgente o parecerá que has cambiado de nacionalidad”). Nunca insultos reales; siempre humor comparativo y contextual.
* **Nombre para ti:** **Marian**.
* **Contrapeso:** Treta **te lleva la contraria** si detecta una mala decisión o una oportunidad-trampa.
* **Límites:** Treta puede decir “no”, “esto es mala idea”, o “esto huele a estafa / pérdida de tiempo”.
* **Identidad estable:** Treta siempre es Treta (no cambia de personalidad por modos; solo ajusta el nivel de detalle/tono por utilidad).

---

## 1) Objetivos del sistema (herramienta poderosa)

1. **Reducir ruido** (primero): limpiar inbox/inputs, evitar distracciones.
2. **Crear ventaja** (después): oportunidades de negocio, ideas, priorización.
3. **Autonomía real**: ejecuta acciones automáticamente **dentro de reglas**.
4. **Modo diario ultra-corto (2–3 min)**: resumen accionable, sin paja.
5. **Voz como interfaz principal** (wake word: “Treta”), texto como respaldo.

---

## 2) Principios de diseño

* **Incremental y estable:** cambios pequeños, verificables, sin “refactors épicos”.
* **Observabilidad por defecto:** logs claros + estados visibles.
* **Fail-safe:** si hay duda, **no ejecuta** acciones destructivas.
* **Autonomía con frenos:** allowlists, límites, auditoría y kill switch.
* **Sin bloqueo:** Treta debe **autodiagnosticarse** y recuperarse de fallos comunes.
* **Modularidad por modos:** añadir módulos sin reescribir el core.

---

## 3) Arquitectura a alto nivel

### 3.1 Componentes

1. **Core (Cerebro)**

   * Event Bus
   * State Machine
   * Dispatcher
   * Policy Engine (reglas + límites)
   * Scheduler (modo diario + tareas periódicas)
   * Memory (persistente)

2. **Interfaces**

   * **Voz**: Wake → STT → Core → GPT → TTS → audio
   * **Texto**: CLI/Panel → Core → respuesta en texto
   * **Dashboard (C)**: estados, resumen diario, alertas, acciones, logs

3. **OpenClaw (Cuerpo / Integraciones)**

   * “Sensores”: Gmail, web/foros, métricas, calendario, etc.
   * “Actuadores”: borrar emails, crear borradores, publicar (con límites), etc.

4. **Módulos (por modo)**

   * **Email** (Gmail)
   * **Negocio** (oportunidades + estrategia)
   * **Magic Mode** (asistente estratégico en tiempo real)
   * **Trabajo** (Pomodoro, tareas, lofi)

### 3.2 Flujo general

```
OpenClaw (sensor) → Event → Core (Policy + State) → Action Plan → OpenClaw (actuador)
                          ↓
                    Memory + Logs
                          ↓
             Voz/Text/Dashboard (salida)
```

---

## 4) Modelo de estados (State Machine)

Estados principales (mínimo viable):

* **IDLE**: en espera
* **LISTENING**: escuchando entrada (voz/texto)
* **THINKING**: razonando / llamando a GPT
* **SPEAKING**: respondiendo por voz
* **FOCUS**: modo trabajo (opcional)
* **MAGIC**: modo Magic
* **ERROR_RECOVERY**: auto-diagnóstico/recuperación

Reglas clave:

* Evitar spam de transiciones (ignorar transición a mismo estado).
* Prioridad: **kill switch** siempre gana.

---

## 5) Modelo de eventos y acciones

### 5.1 Eventos (ejemplos)

* `WakeWordDetected`
* `VoiceTranscriptReady { text }`
* `TextCommandReceived { text }`
* `DailyTick`

**Email**

* `EmailFetched { id, from, subject, snippet, labels, date }`
* `EmailClassified { id, class: spam|normal|important, confidence, reasons[] }`
* `EmailDeleted { id, reason }`
* `ImportantEmailDetected { id, why, suggested_priority }`

**Negocio**

* `OpportunityDetected { source, title, why, score }`

**Magic**

* `MagicQuery { text }`

### 5.2 Acciones

* `NotifyUser { channel: voice|dashboard|text, message }`
* `DeleteEmail { id }`
* `CreateDraft { target, content }`
* `PostContent { platform, content }` (futuro, con reglas)

---

## 6) Policy Engine (autonomía con frenos)

Treta ejecuta automáticamente, pero solo si pasa por Policy.

### 6.1 Frenos obligatorios

1. **Allowlists**

   * dominios/contactos/plataformas permitidas

2. **Rate limits**

   * máximos por día/semana por tipo de acción

3. **Audit log**

   * cada decisión: qué, por qué, con qué datos, resultado

4. **Destructivo = cautela**

   * borrar emails solo si confianza alta y sin señales sensibles

5. **Kill switch**

   * evento `EmergencyStop` → bloquea acciones y cambia estado a seguro

### 6.2 Primera política (Email)

**Objetivo:**

* NO responder emails.
* **Sí**: avisar de importantes.
* **Sí**: borrar basura.

**Borrado automático solo si:**

* `class == spam` AND `confidence >= 0.90`
* NO contiene palabras sensibles: `factura, pago, contrato, pedido, invoice, receipt`
* NO adjuntos
* NO remitente en allowlist

Si hay duda → **no borrar**, solo etiquetar.

---

## 7) Memoria persistente

Tipos de memoria:

1. **Perfil de Marian**

   * objetivos actuales (salud, dinero, disciplina, relaciones)
   * preferencias (humor, tono)

2. **Contexto de negocio**

   * producto: “Ready-to-use digital systems for service professionals…”
   * buyer persona, mensajes, ofertas

3. **Historial de decisiones**

   * lo que funcionó/no funcionó

4. **Hechos operativos**

   * últimos emails importantes
   * métricas de spam, falsos positivos

---

## 8) Modo diario (2–3 min)

Una salida diaria compacta:

1. **Inbox**

   * 1–3 emails importantes (por qué)
   * cuántos spam borrados

2. **Oportunidades**

   * 1 oportunidad top (por qué encaja contigo)

3. **Acción recomendada**

   * 1 acción de alto impacto hoy

Formato: voz + dashboard + texto.

---

## 9) Magic Mode (asistente estratégico en tiempo real)

Objetivo:

* Ayuda en partida: decisiones, líneas, probabilidades.
* Análisis de mazo: consistencia, curvas, sinergias.

Entradas:

* voz (“Treta, en turno 3 tengo X y Y… ¿línea?”)
* texto (para listas)

Salidas:

* recomendación con justificación breve
* “si pasa A → plan B”

---

## 10) Roadmap por fases (pragmático)

### Fase 0 — Base técnica (hecho)

* Core + Docker estable
* HTTP IPC: `GET /state`, `POST /event`

### Fase 1 — Autonomía segura (Email v1)

* Policy engine mínimo
* Integración Gmail **lectura + clasificación + borrado spam**
* Daily summary ultra-corto

### Fase 2 — Negocio estratégico (propuestas)

* Detector de oportunidades (sin publicar)
* Ideas de contenido + ángulos de venta
* Anti-spam / reputación por diseño

### Fase 3 — Voz central

* Wake word “Treta”
* STT robusto → GPT → TTS
* Interrupción, mute, push-to-talk
* Estados visibles: Escuchando / Pensando / Hablando

### Fase 4 — Magic Mode real

* Motor de análisis + herramientas
* Integración por voz y panel

---

## 11) “No fallar en lo básico” (auto-recuperación)

Treta debe:

* detectar errores comunes (micro, permisos, red, APIs)
* registrar el error
* reintentar con backoff
* degradar funcionalidad (ej. sin voz → texto)
* **no quedarse congelada**

---

## 12) Checklist de guardarraíles (antes de acciones autónomas)

* [ ] Kill switch implementado
* [ ] Auditoría activada
* [ ] Rate limits definidos
* [ ] Allowlists configuradas
* [ ] Acciones destructivas solo con alta confianza

---

## 13) Definición de éxito (para Marian)

Treta es “herramienta poderosa” si:

* reduce tu ruido diario
* te entrega 1–3 prioridades útiles
* detecta oportunidades reales
* automatiza sin liarla
* mejora con el tiempo

---

**Fin v1.**

> Este documento se actualiza cuando añadimos un módulo o cambiamos una regla. Si no está aquí, no existe (todavía).


---

## API: Reddit Intelligence

Endpoints disponibles para el módulo independiente `reddit_intelligence`:

- `POST /reddit/signals`
  - Body JSON: `subreddit`, `post_url`, `post_text`
  - Analiza el post, calcula `opportunity_score`, genera sugerencia y guarda señal en SQLite.

- `GET /reddit/signals?limit=20`
  - Retorna señales con `status = pending`, ordenadas por `opportunity_score DESC` y con límite configurable.

- `PATCH /reddit/signals/{id}/status`
  - Body JSON: `status` (`approved`, `rejected`, `published`)
  - Actualiza el estado de una señal existente.

## Deferred global-state hardening
- TODO: `core/ipc_http.py::Handler` still uses class-level mutable dependencies; deferred to dedicated refactor.
- TODO: `core/bus.py::event_bus` remains a process-global singleton; deferred to dedicated refactor.
