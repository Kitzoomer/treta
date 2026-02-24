"""
Discovery notes (Phase 0):
- Decision points are implemented in core/autonomy_policy_engine.py, core/strategy_decision_engine.py,
  core/decision_engine.py, and action execution in core/strategy_action_execution_layer.py.
- SQLite wiring is centralized in core/storage.py (Storage.conn) and schema evolution runs through
  core/migrations/runner.py + migration files in core/migrations/.
- Existing persistence style uses small helper stores and parameterized sqlite3 statements.
- This module is intentionally minimal and additive to keep architecture unchanged.
"""

from __future__ import annotations


from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

REDACT_KEYS = {"token", "secret", "api_key", "authorization"}


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_decision_logs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            action_type TEXT,
            decision TEXT NOT NULL,
            risk_score REAL,
            autonomy_score REAL,
            policy_name TEXT,
            policy_snapshot_json TEXT,
            inputs_json TEXT,
            outputs_json TEXT,
            reason TEXT,
            correlation_id TEXT,
            status TEXT NOT NULL DEFAULT 'recorded',
            error TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_logs_created_at ON decision_logs(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_logs_entity ON decision_logs(entity_type, entity_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_decision_logs_correlation ON decision_logs(correlation_id)")


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value)
    except TypeError:
        return json.dumps(str(value))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in REDACT_KEYS:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def create_decision_log(conn: sqlite3.Connection, log: dict) -> int:
    created_at = str(log.get("created_at") or _utc_iso_now())
    updated_at = str(log.get("updated_at") or _utc_iso_now())
    row = {
        "created_at": created_at,
        "decision_type": str(log.get("decision_type") or "unknown"),
        "entity_type": log.get("entity_type"),
        "entity_id": None if log.get("entity_id") is None else str(log.get("entity_id")),
        "action_type": log.get("action_type"),
        "decision": str(log.get("decision") or "UNKNOWN"),
        "risk_score": log.get("risk_score"),
        "autonomy_score": log.get("autonomy_score"),
        "policy_name": log.get("policy_name"),
        "policy_snapshot_json": _json_dump(_redact(log.get("policy_snapshot_json"))),
        "inputs_json": _json_dump(_redact(log.get("inputs_json"))),
        "outputs_json": _json_dump(_redact(log.get("outputs_json"))),
        "reason": log.get("reason"),
        "correlation_id": log.get("correlation_id"),
        "status": str(log.get("status") or "recorded"),
        "error": log.get("error"),
        "updated_at": updated_at,
    }
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO decision_logs (
            created_at, decision_type, entity_type, entity_id, action_type, decision,
            risk_score, autonomy_score, policy_name, policy_snapshot_json, inputs_json,
            outputs_json, reason, correlation_id, status, error, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["created_at"],
            row["decision_type"],
            row["entity_type"],
            row["entity_id"],
            row["action_type"],
            row["decision"],
            row["risk_score"],
            row["autonomy_score"],
            row["policy_name"],
            row["policy_snapshot_json"],
            row["inputs_json"],
            row["outputs_json"],
            row["reason"],
            row["correlation_id"],
            row["status"],
            row["error"],
            row["updated_at"],
        ),
    )
    return int(cur.lastrowid)


def update_decision_log_status(conn: sqlite3.Connection, id: int, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE decision_logs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
        (status, error, _utc_iso_now(), int(id)),
    )


def _decode_item(row: sqlite3.Row | tuple, columns: list[str]) -> dict[str, Any]:
    item = dict(zip(columns, row))
    for key in ("policy_snapshot_json", "inputs_json", "outputs_json"):
        raw = item.get(key)
        if isinstance(raw, str) and raw:
            try:
                item[key] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    return item


def list_recent_decision_logs(conn: sqlite3.Connection, limit: int = 50, decision_type: str | None = None) -> list[dict[str, Any]]:
    safe_limit = max(min(int(limit), 500), 1)
    columns = [
        "id", "created_at", "decision_type", "entity_type", "entity_id", "action_type", "decision",
        "risk_score", "autonomy_score", "policy_name", "policy_snapshot_json", "inputs_json",
        "outputs_json", "reason", "correlation_id", "status", "error", "updated_at",
    ]
    if decision_type:
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM decision_logs WHERE decision_type = ? ORDER BY created_at DESC LIMIT ?",
            (decision_type, safe_limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {', '.join(columns)} FROM decision_logs ORDER BY created_at DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return [_decode_item(row, columns) for row in rows]


def get_decision_logs_for_entity(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(min(int(limit), 500), 1)
    columns = [
        "id", "created_at", "decision_type", "entity_type", "entity_id", "action_type", "decision",
        "risk_score", "autonomy_score", "policy_name", "policy_snapshot_json", "inputs_json",
        "outputs_json", "reason", "correlation_id", "status", "error", "updated_at",
    ]
    rows = conn.execute(
        f"SELECT {', '.join(columns)} FROM decision_logs WHERE entity_type = ? AND entity_id = ? ORDER BY created_at DESC LIMIT ?",
        (entity_type, entity_id, safe_limit),
    ).fetchall()
    return [_decode_item(row, columns) for row in rows]