from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_action_id ON action_executions(action_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_action_executions_status ON action_executions(status)")

