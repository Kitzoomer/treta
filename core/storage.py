import os
import sqlite3
import threading
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_db_path() -> Path:
    data_root = Path(os.getenv("TRETA_DATA_DIR", "./.treta_data"))
    return data_root / "memory" / "treta.sqlite"


class Storage:
    def __init__(self):
        self.db_path = get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")
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
    ) -> str:
        row_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
            """
            INSERT INTO decision_logs (
                id, timestamp, engine, input_snapshot, computed_score, rules_applied,
                decision, risk_level, expected_impact_score, auto_executed, request_id, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                now,
                engine,
                json.dumps(input_snapshot) if input_snapshot is not None else None,
                computed_score,
                json.dumps(rules_applied) if rules_applied is not None else None,
                decision,
                risk_level,
                expected_impact_score,
                auto_executed,
                request_id,
                json.dumps(metadata) if metadata is not None else None,
            ),
            )
            self.conn.commit()
        return row_id

    def list_decision_logs(self, limit: int = 50) -> list[dict]:
        safe_limit = max(min(int(limit), 500), 1)
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
            """
            SELECT id, timestamp, engine, input_snapshot, computed_score, rules_applied,
                   decision, risk_level, expected_impact_score, auto_executed, request_id, metadata
            FROM decision_logs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
                (safe_limit,),
            )
            rows = cur.fetchall()
        keys = [
            "id",
            "timestamp",
            "engine",
            "input_snapshot",
            "computed_score",
            "rules_applied",
            "decision",
            "risk_level",
            "expected_impact_score",
            "auto_executed",
            "request_id",
            "metadata",
        ]
        items = []
        for row in rows:
            item = dict(zip(keys, row))
            for key in ("input_snapshot", "rules_applied", "metadata"):
                raw = item.get(key)
                if raw:
                    try:
                        item[key] = json.loads(raw)
                    except json.JSONDecodeError:
                        pass
            items.append(item)
        return items
