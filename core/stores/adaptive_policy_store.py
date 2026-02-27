from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlite3


class AdaptivePolicyStore:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def load(self, scope: str = "global") -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT state_json FROM adaptive_policy_state WHERE scope = ?",
            (scope,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row[0] or "{}"))
        return payload if isinstance(payload, dict) else None

    def save(self, state: dict[str, Any], scope: str = "global") -> None:
        now = datetime.now(timezone.utc).isoformat()
        serialized = json.dumps(state)
        self._conn.execute(
            """
            INSERT INTO adaptive_policy_state (scope, state_json, updated_at, version)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(scope) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at,
                version = adaptive_policy_state.version + 1
            """,
            (scope, serialized, now),
        )
        self._conn.commit()

    def ensure_import_from_json_once(self, json_path: str, scope: str = "global") -> bool:
        path = Path(json_path)
        row = self._conn.execute(
            "SELECT migrated_from_json FROM adaptive_policy_state WHERE scope = ?",
            (scope,),
        ).fetchone()
        already_migrated = row is not None and int(row[0] or 0) == 1
        if already_migrated:
            return False
        if not path.exists():
            return False

        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return False

        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO adaptive_policy_state (scope, state_json, updated_at, version, migrated_from_json)
            VALUES (?, ?, ?, 1, 1)
            ON CONFLICT(scope) DO UPDATE SET
                state_json = CASE
                    WHEN adaptive_policy_state.migrated_from_json = 0 THEN excluded.state_json
                    ELSE adaptive_policy_state.state_json
                END,
                updated_at = CASE
                    WHEN adaptive_policy_state.migrated_from_json = 0 THEN excluded.updated_at
                    ELSE adaptive_policy_state.updated_at
                END,
                version = CASE
                    WHEN adaptive_policy_state.migrated_from_json = 0 THEN adaptive_policy_state.version + 1
                    ELSE adaptive_policy_state.version
                END,
                migrated_from_json = 1
            """,
            (scope, json.dumps(loaded), now),
        )
        self._conn.commit()

        post_row = self._conn.execute(
            "SELECT migrated_from_json FROM adaptive_policy_state WHERE scope = ?",
            (scope,),
        ).fetchone()
        return post_row is not None and int(post_row[0] or 0) == 1 and not already_migrated
