from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_outcomes_strategy_type ON decision_outcomes(strategy_type)")
