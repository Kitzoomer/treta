from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_product_suggestions (
            id TEXT PRIMARY KEY,
            pain_category TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            avg_urgency REAL NOT NULL,
            monetization_level TEXT NOT NULL,
            suggested_product TEXT NOT NULL,
            positioning_angle TEXT,
            estimated_price_range TEXT,
            generated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
