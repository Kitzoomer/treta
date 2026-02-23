from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_demand_validations (
            id TEXT PRIMARY KEY,
            pain_category TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            avg_urgency REAL NOT NULL,
            monetization_level TEXT NOT NULL,
            demand_strength TEXT NOT NULL,
            launch_priority_score REAL NOT NULL,
            recommended_action TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            validated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
