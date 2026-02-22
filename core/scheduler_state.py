from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.persistence.json_io import atomic_read_json

_DEFAULT_DATA_DIR = "./.treta_data"
_STATE_FILENAME = "scheduler_state.json"
_DB_RELATIVE_PATH = Path("memory") / "treta.sqlite"


def _data_dir() -> Path:
    return Path(os.getenv("TRETA_DATA_DIR", _DEFAULT_DATA_DIR))


def _scheduler_state_path() -> Path:
    return _data_dir() / _STATE_FILENAME


def _db_path() -> Path:
    return _data_dir() / _DB_RELATIVE_PATH


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduler_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _migrate_json_if_needed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    existing = {
        row[0]: row[1]
        for row in cur.execute("SELECT key, value FROM scheduler_state WHERE key IN (?, ?)", ("last_run_date", "last_run_timestamp"))
    }
    if existing:
        return

    json_path = _scheduler_state_path()
    if not json_path.exists():
        return

    state = atomic_read_json(json_path, default={})
    if not isinstance(state, dict):
        return

    last_run_date = state.get("last_run_date")
    last_run_timestamp = state.get("last_run_timestamp")
    now = datetime.now(timezone.utc).isoformat()

    if isinstance(last_run_date, str):
        cur.execute(
            "INSERT OR REPLACE INTO scheduler_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("last_run_date", last_run_date, now),
        )
    if isinstance(last_run_timestamp, str):
        cur.execute(
            "INSERT OR REPLACE INTO scheduler_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("last_run_timestamp", last_run_timestamp, now),
        )

    if isinstance(last_run_date, str) or isinstance(last_run_timestamp, str):
        conn.commit()

    if json_path.exists():
        json_path.unlink()


def load_scheduler_state() -> dict[str, str]:
    with _connect() as conn:
        _migrate_json_if_needed(conn)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM scheduler_state WHERE key IN (?, ?)", ("last_run_date", "last_run_timestamp"))
        rows = cur.fetchall()

    return {
        key: value
        for key, value in rows
        if isinstance(key, str) and isinstance(value, str)
    }


def save_scheduler_state(date_str: str, timestamp_str: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO scheduler_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("last_run_date", date_str, now),
        )
        cur.execute(
            "INSERT OR REPLACE INTO scheduler_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("last_run_timestamp", timestamp_str, now),
        )
        conn.commit()
