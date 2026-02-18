# UI ↔ Backend Coherence Audit (Treta)

## Scope
- `ui/app.js` router, render flow, refresh loop, settings actions, observability surface.
- Backend endpoint coverage checked against `core/ipc_http.py`, `core/control.py`, and `core/reddit_intelligence/router.py`.

## Findings

### 1) Invalid hash routes silently fallback with no user feedback
- **Severity:** High
- **Evidence:** Route resolver previously defaulted directly to home for unknown hashes.
- **Impact:** Navigation issues were hidden; users could not distinguish typo/broken route from intended home navigation.
- **Minimal fix:** Added route normalization helper (`normalizeRoute`) plus invalid-route banner behavior and timed redirect to `#/home` (~3s).

### 2) Refresh loop had all-or-nothing failure behavior and no per-slice diagnostics
- **Severity:** High
- **Evidence:** Single `Promise.all` for all endpoints in one `try/catch`; one failed endpoint could mask freshness of others.
- **Impact:** Partial backend outages reduced UI coherence and observability.
- **Minimal fix:** Split refresh into slice-based tasks (`system`, `strategy`, `reddit`) with independent error tracking and refresh timestamps.

### 3) Backend connection state was implicit, causing preview/local confusion
- **Severity:** High
- **Evidence:** No explicit connected/disconnected signal tied to core endpoint health.
- **Impact:** In backend-less preview contexts the UI looked "broken" without explanation.
- **Minimal fix:** Added `Backend: CONNECTED/DISCONNECTED` indicator driven by `/system/integrity` success/failure.

### 4) Settings post-actions were not giving robust in-place user feedback
- **Severity:** High
- **Evidence:** Save/scan rerendered but had no durable transient success state; scan result coherence across dashboard/settings was weak.
- **Impact:** Users could interpret actions as no-op or stale.
- **Minimal fix:** Save and Run Scan now update local state immediately, trigger rerender/refresh, and show transient success feedback.

### 5) Missing dashboard exposure for key observability endpoints
- **Severity:** Medium
- **Evidence:** `/reddit/today_plan` and `/reddit/signals` were surfaced; `/reddit/daily_actions` lacked explicit UI exposure.
- **Impact:** Incomplete operational overview.
- **Minimal fix:** Added dashboard “More Observability” collapsible section with today-plan summary, daily-actions count, and top signal snapshot.

### 6) No lightweight diagnostics panel for refresh/error tracing
- **Severity:** Medium
- **Evidence:** No UI visibility for per-slice last refresh/error status.
- **Impact:** Harder to debug stale/partial data behavior.
- **Minimal fix:** Added hidden-by-default diagnostics toggle displaying last refresh timestamps and last API error per core slice.

## Implemented Fix Set (Critical/High)
- Route normalization + invalid-route notice and redirect.
- Slice-based refresh guardrails, per-slice freshness timestamps, last API error capture.
- Backend connected/disconnected indicator.
- Settings save/scan in-place coherence improvements with transient success feedback.

## Notes
- No backend endpoint contracts were changed.
- Changes intentionally limited to `ui/app.js` + this audit document.
