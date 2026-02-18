import os
import sqlite3
from pathlib import Path
from typing import Optional

DATA_ROOT = Path(os.getenv("TRETA_DATA_DIR", "./.treta_data"))
DB_PATH = DATA_ROOT / "memory" / "treta.sqlite"


class Storage:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        self.conn.commit()

    def set_state(self, key: str, value: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_state(self, key: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None
