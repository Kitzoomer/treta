from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_actions (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            status TEXT,
            payload_json TEXT,
            decision_id TEXT,
            event_id TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_status ON strategy_actions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_event_id ON strategy_actions(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_actions_decision_id ON strategy_actions(decision_id)")
