from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS adaptive_policy_state (
            scope TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            migrated_from_json INTEGER NOT NULL DEFAULT 0
        )
        """
    )
