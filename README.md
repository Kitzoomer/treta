# TRETA

## Internal Audit

Run locally:

```bash
make audit
# or
python scripts/audit.py
```

After merge:

```bash
git pull
docker compose down
docker compose up --build
```

Manual verification:

```bash
curl http://localhost:7777/health
curl http://localhost:7777/ready
```

## Decision Logs (Autonomy Traceability)

TRETA now writes persistent decision logs to SQLite (`decision_logs`) for autonomy and strategy decisions.
This audit trail helps answer:
- Why did TRETA run autonomously?
- Which policy caused a denial?
- What action/entity was affected?

Query examples:

```bash
curl "http://localhost:7777/decision-logs?limit=50"
curl "http://localhost:7777/decision-logs?limit=50&decision_type=autonomy"
curl "http://localhost:7777/decision-logs/entity?entity_type=action&entity_id=action-000001&limit=20"
```


## HTTP Auth hardening

Default behavior is now secure-by-default:
- `TRETA_DEV_MODE=0` (default)
- `TRETA_REQUIRE_TOKEN=1` (default)

When token is required and `TRETA_API_TOKEN` is empty, server starts in **degraded** mode:
- Mutating endpoints (`POST`/`PUT`/`DELETE`/`PATCH`) that are protected return `503 auth_degraded`.
- Read-only health endpoints remain available (`/health`, `/health/live`).

Development options:
- Set `TRETA_DEV_MODE=1` to keep permissive behavior (no token required).
- Or set `TRETA_REQUIRE_TOKEN=0` for explicit permissive mode.

Recommended local run with token:

```bash
export TRETA_API_TOKEN=change-me
export TRETA_DEV_MODE=0
export TRETA_REQUIRE_TOKEN=1
```

Manual checks with curl:

```bash
# Should return 401 when token is required and missing/invalid.
curl -i -X POST http://localhost:7777/opportunities/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"id":"opp-1"}'

# Should return 200 with valid bearer token.
curl -i -X POST http://localhost:7777/opportunities/evaluate \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TRETA_API_TOKEN}" \
  -d '{"id":"opp-1"}'

# Health should report auth status (ok/degraded).
curl -s http://localhost:7777/health
```
