from __future__ import annotations

import sqlite3

from core.persistence.decision_logs import (
    create_decision_log,
    ensure_decision_logs_table,
    get_decision_logs_for_entity,
    list_recent_decision_logs,
    update_decision_log_status,
)


def test_decision_logs_insert_query_update() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        ensure_decision_logs_table(conn)
        row_id = create_decision_log(
            conn,
            {
                "decision_type": "autonomy",
                "entity_type": "action",
                "entity_id": "action-1",
                "action_type": "execute",
                "decision": "ALLOW",
                "risk_score": 2.0,
                "policy_name": "AutonomyPolicyEngine",
                "inputs_json": {"id": "action-1"},
                "outputs_json": {"status": "executed"},
                "reason": "test",
                "correlation_id": "req-1",
            },
        )
        conn.commit()

        recent = list_recent_decision_logs(conn, limit=10)
        assert recent and recent[0]["id"] == row_id
        assert recent[0]["decision_type"] == "autonomy"

        entity_items = get_decision_logs_for_entity(conn, entity_type="action", entity_id="action-1", limit=10)
        assert entity_items and entity_items[0]["entity_id"] == "action-1"

        update_decision_log_status(conn, row_id, status="executed", error=None)
        conn.commit()

        updated = list_recent_decision_logs(conn, limit=1)[0]
        assert updated["status"] == "executed"
    finally:
        conn.close()
