# Treta Architecture (v1.0.0 Freeze)

This document freezes Treta's architecture and domain contracts for `v1.0.0`.

## System layers

Treta is organized into these high-level layers:

1. **UI (SPA)**
   - Browser-based single-page interface (`ui/`) consuming HTTP endpoints.
2. **HTTP routing layer**
   - Request/response boundary (`core/ipc_http.py`) that validates availability and maps routes to control/domain operations.
3. **Control layer**
   - Application orchestration (`core/control.py`) handling events and coordinating stores and engines.
4. **Domain policy layer**
   - Explicit lifecycle rules and integrity policy (`core/domain/integrity.py`).
5. **Stores (JSON persistence)**
   - File-backed JSON stores for proposals/plans/launches and related entities.
6. **Event bus**
   - In-process event queue (`core/bus.py`) for decoupled event production/consumption.

## Proposal lifecycle

Canonical proposal status progression:

`draft → approved → building → ready_to_launch → ready_for_review → launched (active launch)`

Allowed transitions:

- `draft` → `approved`, `rejected`
- `approved` → `building`, `archived`
- `building` → `ready_to_launch`
- `ready_to_launch` → `ready_for_review`
- `ready_for_review` → `launched`, `executed`
- `launched` → `archived`
- `rejected` → `archived`
- `archived` → _(terminal)_

## Launch lifecycle

Canonical launch status progression:

`draft → active → paused → archived`

Allowed transitions:

- `draft` → `active`, `archived`
- `active` → `paused`, `archived`
- `paused` → `active`, `archived`
- `archived` → _(terminal)_

Relationship to proposals:

- Launches are created from proposals.
- Launch activation corresponds to a proposal reaching launched/active-launch state.
- Draft or rejected proposals must not have an active launch.

## Domain invariants

The v1 domain contracts include:

- **Single active proposal execution**: only one proposal execution may be active at a time.
- **No invalid active launches**: draft/rejected proposals cannot have an active launch.
- **Plan build precondition**: plans are buildable only from `PLAN_BUILDABLE_STATUSES`.
- **Integrity failure contract**: `GET /system/integrity` returns `503` when store loading fails.

## JSON corruption strategy

On JSON decode/load corruption for store files:

1. Rename corrupt file to `*.corrupt`.
2. Recover by using an empty in-memory store.
3. Emit a diagnostic signal (warning/diagnostic flag) via logging and integrity diagnostics.

## Event bus semantics

The event bus contract for v1:

- **Process-local only**: queue/history live within one process.
- **No cross-process guarantees**: no durability or ordering guarantees across multiple processes.
- **Tests must reset explicitly**: tests interacting with bus state should explicitly reset/avoid leaked history between cases.
