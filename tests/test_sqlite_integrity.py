from __future__ import annotations

import os
import sqlite3

from core.migrations.runner import run_migrations
from core.storage import get_db_path


def _resolve_db_path() -> str:
    return os.getenv("TRETA_DB_PATH") or str(get_db_path())


def test_sqlite_integrity_and_safe_rw() -> None:
    db_path = _resolve_db_path()
    conn = sqlite3.connect(db_path)
    try:
        run_migrations(conn)
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        assert row is not None
        assert row[0] == "ok"

        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if "state" in tables:
            conn.execute("BEGIN")
            conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", ("__audit_probe", "ok"))
            probe = conn.execute("SELECT value FROM state WHERE key = ?", ("__audit_probe",)).fetchone()
            assert probe is not None and probe[0] == "ok"
            conn.rollback()
        else:
            conn.execute("CREATE TABLE IF NOT EXISTS __audit_tmp (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO __audit_tmp (value) VALUES ('ok')")
            probe = conn.execute("SELECT value FROM __audit_tmp LIMIT 1").fetchone()
            assert probe is not None and probe[0] == "ok"
            conn.execute("DELETE FROM __audit_tmp")
            conn.commit()
    finally:
        conn.close()
