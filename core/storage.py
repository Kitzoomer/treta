import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from core.persistence.decision_logs import (
    create_decision_log,
    ensure_decision_logs_table,
    get_decision_logs_for_entity as query_decision_logs_for_entity,
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
        self.conn.execute("PRAGMA foreign_keys = ON;")
        ensure_decision_logs_table(self.conn)
        self._lock = threading.Lock()

    def set_state(self, key: str, value: str):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
                (key, value),
            )
            self.conn.commit()

    def get_state(self, key: str) -> Optional[str]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cur.fetchone()
        return row[0] if row else None

    def create_decision_log(self, log: dict) -> int:
        with self._lock:
            row_id = create_decision_log(self.conn, log)
            self.conn.commit()
        return row_id

    def update_decision_log_status(self, id: int, status: str, error: str | None = None) -> None:
        with self._lock:
            update_decision_log_status(self.conn, id=id, status=status, error=error)
            self.conn.commit()

    def list_recent_decision_logs(self, limit: int = 50, decision_type: str | None = None) -> list[dict]:
        with self._lock:
            return list_recent_decision_logs(self.conn, limit=limit, decision_type=decision_type)

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
                "status": "executed" if auto_executed else "recorded",
                "entity_type": "action" if auto_executed else None,
                "action_type": risk_level,
            }
        )

    def list_decision_logs(self, limit: int = 50) -> list[dict]:
        items = self.list_recent_decision_logs(limit=limit)
        for item in items:
            if "engine" not in item:
                item["engine"] = item.get("decision_type")
            if "request_id" not in item:
                item["request_id"] = item.get("correlation_id")
        return items
