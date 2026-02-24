from __future__ import annotations

import sqlite3

from core.persistence.decision_logs import ensure_decision_logs_table


def test_decision_logs_schema_columns() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        ensure_decision_logs_table(conn)
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(decision_logs)").fetchall()
        }
        expected = {
            "id",
            "created_at",
            "decision_type",
            "entity_type",
            "entity_id",
            "action_type",
            "decision",
            "risk_score",
            "autonomy_score",
            "policy_name",
            "policy_snapshot_json",
            "inputs_json",
            "outputs_json",
            "reason",
            "correlation_id",
            "status",
            "error",
            "updated_at",
        }
        assert expected.issubset(cols)
    finally:
        conn.close()
