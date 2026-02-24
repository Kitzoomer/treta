from __future__ import annotations

import sqlite3

from core.persistence.decision_logs import ensure_decision_logs_table


def _has_new_schema(conn: sqlite3.Connection) -> bool:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(decision_logs)").fetchall()}
    return "created_at" in cols and "decision_type" in cols


def upgrade(conn: sqlite3.Connection) -> None:
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='decision_logs'"
    ).fetchone()
    if existing is None:
        ensure_decision_logs_table(conn)
        conn.commit()
        return

    if _has_new_schema(conn):
        ensure_decision_logs_table(conn)
        conn.commit()
        return

    conn.execute("ALTER TABLE decision_logs RENAME TO decision_logs_legacy")
    ensure_decision_logs_table(conn)
    conn.execute(
        """
        INSERT INTO decision_logs (
            created_at, decision_type, entity_type, entity_id, action_type, decision,
            risk_score, autonomy_score, policy_name, policy_snapshot_json, inputs_json,
            outputs_json, reason, correlation_id, status, error, updated_at
        )
        SELECT
            COALESCE(timestamp, datetime('now')),
            COALESCE(engine, 'legacy'),
            NULL,
            NULL,
            NULL,
            COALESCE(decision, 'UNKNOWN'),
            computed_score,
            expected_impact_score,
            engine,
            NULL,
            input_snapshot,
            metadata,
            NULL,
            request_id,
            'recorded',
            NULL,
            COALESCE(timestamp, datetime('now'))
        FROM decision_logs_legacy
        """
    )
    conn.execute("DROP TABLE decision_logs_legacy")
    conn.commit()
