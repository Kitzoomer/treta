from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    base = os.environ.get("TRETA_DATA_DIR", ".")
    return Path(base) / "reddit_intelligence.db"


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_sqlite() -> None:
    with get_connection() as conn:
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
                updated_at TEXT
            )
            """
        )
        conn.commit()
