from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List

from core.persistence.json_io import atomic_read_json, atomic_write_json


class MemoryStore:
    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "memory_store.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Any] = self._load()
        self._conn: sqlite3.Connection | None = None
        self._init_snapshot_db(data_dir)

    def _init_snapshot_db(self, data_dir: Path) -> None:
        db_path = data_dir / "memory" / "treta.sqlite"
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategic_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    snapshot_text TEXT NOT NULL
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_strategic_snapshots_created_at ON strategic_snapshots(created_at)")
            self._conn.commit()
        except sqlite3.Error:
            self._conn = None

    def _default_state(self) -> Dict[str, Any]:
        return {
            "profile": {
                "name": "Marian",
                "objective": "Infoproductos: detectar oportunidades, proponer, construir y ayudar a vender",
                "autonomy_default": "manual",
            },
            "chat_history": [],
        }

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            state = self._default_state()
            self.save(state)
            return state

        loaded = atomic_read_json(self._path, self._default_state())
        if not isinstance(loaded, dict):
            return self._default_state()

        state = self._default_state()
        profile = loaded.get("profile", {})
        if isinstance(profile, dict):
            state["profile"].update({k: v for k, v in profile.items() if isinstance(k, str)})
        chat_history = loaded.get("chat_history", [])
        if isinstance(chat_history, list):
            state["chat_history"] = [dict(item) for item in chat_history if isinstance(item, dict)][-20:]
        return state

    def load(self) -> Dict[str, Any]:
        self._state = self._load()
        return self.snapshot()

    def save(self, state: Dict[str, Any] | None = None) -> None:
        if state is not None:
            self._state = dict(state)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, self._state)

    def snapshot(self) -> Dict[str, Any]:
        return deepcopy(self._state)

    def append_message(self, role: str, text: str, ts: str | None = None) -> Dict[str, Any]:
        message = {
            "role": str(role),
            "text": str(text),
            "ts": ts or datetime.now(timezone.utc).isoformat(),
        }
        history: List[Dict[str, Any]] = self._state.setdefault("chat_history", [])
        history.append(message)
        self._state["chat_history"] = history[-20:]
        self.save()
        return deepcopy(message)

    def save_snapshot(self, snapshot_text: str, ts: str | None = None) -> None:
        if self._conn is None:
            return
        timestamp = ts or datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO strategic_snapshots (created_at, snapshot_text) VALUES (?, ?)",
            (timestamp, str(snapshot_text)),
        )
        self._conn.commit()

    def get_latest_snapshot(self) -> str:
        if self._conn is None:
            return ""
        row = self._conn.execute(
            "SELECT snapshot_text FROM strategic_snapshots ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return ""
        return str(row[0] or "")
