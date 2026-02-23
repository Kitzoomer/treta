from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_pain_analysis (
            id TEXT PRIMARY KEY,
            reddit_signal_id TEXT NOT NULL,
            pain_category TEXT,
            monetization_level TEXT,
            urgency_score REAL,
            analyzed_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
