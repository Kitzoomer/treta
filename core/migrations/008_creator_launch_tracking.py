from __future__ import annotations

import sqlite3



def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_offer_launches (
            id TEXT PRIMARY KEY,
            offer_id TEXT NOT NULL,
            pain_category TEXT NOT NULL,
            monetization_level TEXT NOT NULL,
            launch_date TEXT NOT NULL,
            price REAL NOT NULL,
            sales INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
