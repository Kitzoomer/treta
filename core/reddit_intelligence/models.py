from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_legacy_db_path() -> Path:
    base = os.environ.get("TRETA_DATA_DIR", ".")
    return Path(base) / "reddit_intelligence.db"


def ensure_reddit_signals_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reddit_signals (
            id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            post_url TEXT NOT NULL,
            post_text TEXT NOT NULL,
            detected_pain_type TEXT,
            opportunity_score INTEGER,
            intent_level TEXT,
            suggested_action TEXT,
            generated_reply TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            karma INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            performance_score INTEGER DEFAULT 0,
            mention_used BOOLEAN DEFAULT 0
        )
        """
    )

    existing_cols = {
        row[1]
        for row in cur.execute("PRAGMA table_info(reddit_signals)").fetchall()
    }
    migrations = {
        "karma": "ALTER TABLE reddit_signals ADD COLUMN karma INTEGER DEFAULT 0",
        "replies": "ALTER TABLE reddit_signals ADD COLUMN replies INTEGER DEFAULT 0",
        "performance_score": "ALTER TABLE reddit_signals ADD COLUMN performance_score INTEGER DEFAULT 0",
        "mention_used": "ALTER TABLE reddit_signals ADD COLUMN mention_used BOOLEAN DEFAULT 0",
    }
    for column_name, ddl in migrations.items():
        if column_name not in existing_cols:
            cur.execute(ddl)

    conn.commit()
