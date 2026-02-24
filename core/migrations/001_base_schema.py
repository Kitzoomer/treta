from __future__ import annotations

import sqlite3

from core.persistence.decision_logs import ensure_decision_logs_table


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
    ensure_decision_logs_table(conn)
