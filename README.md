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
