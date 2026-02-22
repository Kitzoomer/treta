from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_logs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            engine TEXT NOT NULL,
            input_snapshot TEXT,
            computed_score REAL,
            rules_applied TEXT,
            decision TEXT NOT NULL,
            risk_level TEXT,
            expected_impact_score REAL,
            auto_executed BOOLEAN,
            request_id TEXT,
            metadata TEXT
        )
        """
    )
