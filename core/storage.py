import os
import sqlite3
import threading
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.persistence.decision_logs import (
    create_decision_log,
    ensure_decision_logs_table,
    get_decision_logs_for_entity as query_decision_logs_for_entity,
    get_latest_decision_log_by_type,
    list_recent_decision_logs,
    update_decision_log_status,
)


def get_db_path() -> Path:
    data_root = Path(os.getenv("TRETA_DATA_DIR", "./.treta_data"))
    return data_root / "memory" / "treta.sqlite"


class Storage:
    def __init__(self):
        self.db_path = get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._logger = logging.getLogger("treta.storage")
        self._configure_connection()
        ensure_decision_logs_table(self.conn)
        self._ensure_runtime_overrides_table()
        self._ensure_processed_events_table()
        self._ensure_decision_outcomes_table()
        self._ensure_action_executions_table()
        self._lock = threading.Lock()


    def _ensure_runtime_overrides_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_overrides (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )

    def _ensure_processed_events_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                processed_at TEXT
            )
            """
        )

    def _ensure_decision_outcomes_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                decision_id TEXT PRIMARY KEY,
                strategy_type TEXT,
                was_autonomous INTEGER,
                predicted_risk REAL,
                revenue_generated REAL DEFAULT 0,
                outcome TEXT,
                evaluated_at TEXT
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_outcomes_strategy_type ON decision_outcomes(strategy_type)")

    def _ensure_action_executions_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                action_type TEXT,
                status TEXT NOT NULL,
                executor TEXT,
                started_at TEXT,
                finished_at TEXT,
                request_id TEXT,
                trace_id TEXT,
                correlation_id TEXT,
                input_payload_json TEXT,
                output_payload_json TEXT,
                error TEXT
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_action_id ON action_executions(action_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_status ON action_executions(status)")

    def _configure_connection(self) -> None:
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")
        wal_mode = str(self.conn.execute("PRAGMA journal_mode;").fetchone()[0]).lower()
        self._logger.info("SQLite configured", extra={"journal_mode": wal_mode, "foreign_keys": 1})

    @contextmanager
    def transaction(self):
        with self._lock:
            try:
                self.conn.execute("BEGIN")
                yield self.conn
            except Exception:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()

    def _build_correlation_id(self, log: dict) -> str | None:
        base = str(log.get("correlation_id") or "").strip()
        request_id = str(log.get("request_id") or "").strip()
        trace_id = str(log.get("trace_id") or "").strip()
        event_id = str(log.get("event_id") or "").strip()
        parts: list[str] = []
        if base:
            parts.append(base)
        if request_id:
            parts.append(f"request:{request_id}")
        if trace_id:
            parts.append(f"trace:{trace_id}")
        if event_id:
            parts.append(f"event:{event_id}")
        if not parts:
            return None
        merged: list[str] = []
        seen = set()
        for part in parts:
            if part not in seen:
                seen.add(part)
                merged.append(part)
        return "|".join(merged)

    def set_state(self, key: str, value: str):
        with self.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_state(self, key: str) -> Optional[str]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cur.fetchone()
        return row[0] if row else None

    def create_decision_log(self, log: dict) -> int:
        payload = dict(log)
        payload["correlation_id"] = self._build_correlation_id(payload)
        with self.transaction() as conn:
            row_id = create_decision_log(conn, payload)
        return row_id

    def update_decision_log_status(self, id: int, status: str, error: str | None = None) -> None:
        with self.transaction() as conn:
            update_decision_log_status(conn, id=id, status=status, error=error)

    def set_runtime_override(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO runtime_overrides (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def get_runtime_override(self, key: str) -> Optional[str]:
        with self._lock:
            row = self.conn.execute("SELECT value FROM runtime_overrides WHERE key = ?", (key,)).fetchone()
        return str(row[0]) if row else None


    def is_event_processed(self, event_id: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM processed_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return row is not None

    def mark_event_processed(self, event_id: str, event_type: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_events (event_id, event_type, processed_at)
                VALUES (?, ?, ?)
                """,
                (event_id, event_type, now),
            )

    def list_recent_processed_events(self, limit: int = 50) -> list[dict]:
        safe_limit = max(min(int(limit), 500), 1)
        query = """
            SELECT pe.event_id, pe.event_type, pe.processed_at,
                   dl.id as decision_id,
                   COALESCE(dl.status, 'processed') as status
            FROM processed_events pe
            LEFT JOIN decision_logs dl
              ON dl.id = (
                SELECT d.id
                FROM decision_logs d
                WHERE d.correlation_id LIKE '%' || pe.event_id || '%'
                ORDER BY d.created_at DESC
                LIMIT 1
              )
            ORDER BY pe.processed_at DESC
            LIMIT ?
        """
        with self._lock:
            rows = self.conn.execute(query, (safe_limit,)).fetchall()
        return [
            {
                "event_id": str(row[0]),
                "event_type": str(row[1]) if row[1] is not None else "",
                "processed_at": row[2],
                "decision_id": None if row[3] is None else str(row[3]),
                "status": str(row[4] or "processed"),
            }
            for row in rows
        ]

    def get_strategic_metrics_summary(self) -> dict:
        with self._lock:
            totals = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total_decisions,
                    SUM(CASE WHEN was_autonomous = 1 THEN 1 ELSE 0 END) as total_autonomous,
                    SUM(CASE WHEN was_autonomous = 0 THEN 1 ELSE 0 END) as total_manual,
                    COALESCE(SUM(revenue_generated), 0) as total_revenue,
                    COALESCE(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END), 0) as success_rate
                FROM decision_outcomes
                """
            ).fetchone()
            rows = self.conn.execute(
                """
                SELECT strategy_type, COALESCE(SUM(revenue_generated), 0)
                FROM decision_outcomes
                GROUP BY strategy_type
                """
            ).fetchall()

        revenue_map = {str(row[0] or "unknown"): float(row[1] or 0) for row in rows}
        return {
            "total_decisions": int(totals[0] or 0),
            "total_autonomous": int(totals[1] or 0),
            "total_manual": int(totals[2] or 0),
            "total_revenue": float(totals[3] or 0),
            "success_rate": float(totals[4] or 0),
            "revenue_por_strategy_type": revenue_map,
        }

    def get_strategy_performance(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT
                    strategy_type,
                    COUNT(*) as total_decisions,
                    COALESCE(AVG(revenue_generated), 0) as avg_revenue,
                    COALESCE(AVG(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END), 0) as success_rate,
                    COALESCE(AVG(predicted_risk), 0) as avg_predicted_risk
                FROM decision_outcomes
                GROUP BY strategy_type
                """
            ).fetchall()

        performance: dict[str, dict[str, float | int]] = {}
        for row in rows:
            strategy_type = str(row[0] or "unknown")
            total_decisions = int(row[1] or 0)
            avg_revenue = float(row[2] or 0)
            success_rate = float(row[3] or 0)
            avg_predicted_risk = float(row[4] or 0)
            score = (avg_revenue * success_rate) / (1.0 + avg_predicted_risk)
            performance[strategy_type] = {
                "total_decisions": total_decisions,
                "avg_revenue": avg_revenue,
                "success_rate": success_rate,
                "avg_predicted_risk": avg_predicted_risk,
                "score": score,
            }
        return performance

    def list_recent_decision_logs(self, limit: int = 50, decision_type: str | None = None) -> list[dict]:
        with self._lock:
            return list_recent_decision_logs(self.conn, limit=limit, decision_type=decision_type)

    def get_latest_decision_log_by_type(self, decision_type: str) -> dict | None:
        with self._lock:
            return get_latest_decision_log_by_type(self.conn, decision_type=decision_type)

    def get_decision_logs_for_entity(self, entity_type: str, entity_id: str, limit: int = 50) -> list[dict]:
        with self._lock:
            return query_decision_logs_for_entity(self.conn, entity_type=entity_type, entity_id=entity_id, limit=limit)

    # Backward-compatible adapter used by existing engines/tests.
    def insert_decision_log(
        self,
        *,
        engine: str,
        decision: str,
        input_snapshot: dict | None = None,
        computed_score: float | None = None,
        rules_applied: list[str] | None = None,
        risk_level: str | None = None,
        expected_impact_score: float | None = None,
        auto_executed: bool | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        return self.create_decision_log(
            {
                "decision_type": engine,
                "decision": decision,
                "risk_score": computed_score,
                "autonomy_score": expected_impact_score,
                "policy_name": engine,
                "policy_snapshot_json": {"rules_applied": rules_applied or []},
                "inputs_json": input_snapshot,
                "outputs_json": metadata,
                "reason": (metadata or {}).get("reasoning") if isinstance(metadata, dict) else None,
                "correlation_id": request_id,
                "request_id": request_id,
                "trace_id": trace_id,
                "event_id": event_id,
                "status": "executed" if auto_executed else "recorded",
                "entity_type": "action" if auto_executed else None,
                "action_type": risk_level,
            }
        )

    def _request_id_from_correlation(self, correlation_id: str | None) -> str | None:
        raw = str(correlation_id or "").strip()
        if not raw:
            return None
        for part in raw.split("|"):
            if part.startswith("request:"):
                return part.replace("request:", "", 1)
        if "|" not in raw:
            return raw
        return None

    def list_decision_logs(self, limit: int = 50) -> list[dict]:
        items = self.list_recent_decision_logs(limit=limit)
        for item in items:
            if "engine" not in item:
                item["engine"] = item.get("decision_type")
            if "request_id" not in item:
                item["request_id"] = self._request_id_from_correlation(item.get("correlation_id"))
        return items
