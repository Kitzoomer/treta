from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
from typing import Any


class ActionExecutionStore:
    _TERMINAL_STATUSES = {"success", "failed", "failed_timeout", "skipped"}

    def __init__(self, conn):
        self._conn = conn
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._lock:
            self._conn.execute(
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
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_action_id ON action_executions(action_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_status ON action_executions(status)")
            self._conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _compact_json(self, value: Any, max_len: int = 5000) -> str:
        text = json.dumps(value, ensure_ascii=False)
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}...<trimmed>"

    def create_queued(self, *, action_id: str, action_type: str, executor: str, context: dict[str, Any]) -> int:
        now = self._now()
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO action_executions (
                    action_id, action_type, status, executor,
                    started_at, request_id, trace_id, correlation_id, input_payload_json
                ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    action_type,
                    executor,
                    now,
                    str(context.get("request_id", "") or ""),
                    str(context.get("trace_id", "") or ""),
                    str(context.get("correlation_id", "") or ""),
                    self._compact_json(context),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def mark_running(self, execution_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE action_executions SET status = 'running', started_at = ? WHERE id = ?",
                (self._now(), execution_id),
            )
            self._conn.commit()

    def complete(self, execution_id: int, *, status: str, output_payload: Any = None, error: str | None = None) -> None:
        if status not in self._TERMINAL_STATUSES:
            raise ValueError(f"invalid terminal status: {status}")
        with self._lock:
            self._conn.execute(
                """
                UPDATE action_executions
                SET status = ?,
                    finished_at = ?,
                    output_payload_json = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    status,
                    self._now(),
                    self._compact_json(output_payload if output_payload is not None else {}),
                    str(error or "") or None,
                    execution_id,
                ),
            )
            self._conn.commit()



    def latest_for_action(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, action_id, action_type, status, executor, started_at, finished_at,
                       request_id, trace_id, correlation_id, input_payload_json, output_payload_json, error
                FROM action_executions
                WHERE action_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (action_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def mark_failed_timeout(self, execution_id: int, *, error: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE action_executions
                SET status = 'failed_timeout',
                    finished_at = ?,
                    error = ?
                WHERE id = ?
                """,
                (self._now(), str(error or "execution timeout exceeded"), execution_id),
            )
            self._conn.commit()

    def has_success_for_action(self, action_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM action_executions WHERE action_id = ? AND status = 'success' LIMIT 1",
                (action_id,),
            ).fetchone()
        return row is not None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, action_id, action_type, status, executor, started_at, finished_at,
                       request_id, trace_id, correlation_id, input_payload_json, output_payload_json, error
                FROM action_executions
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_for_action(self, action_id: str, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, action_id, action_type, status, executor, started_at, finished_at,
                       request_id, trace_id, correlation_id, input_payload_json, output_payload_json, error
                FROM action_executions
                WHERE action_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (action_id, safe_limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> dict[str, Any]:
        keys = [
            "id", "action_id", "action_type", "status", "executor", "started_at", "finished_at",
            "request_id", "trace_id", "correlation_id", "input_payload_json", "output_payload_json", "error",
        ]
        item = dict(zip(keys, row))
        return item
