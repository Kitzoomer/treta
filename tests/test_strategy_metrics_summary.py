import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from core.bus import EventBus
from core.ipc_http import start_http_server
from core.migrations.runner import run_migrations
from core.strategy_action_store import StrategyActionStore
from core.storage import get_db_path, Storage


class StrategyMetricsSummaryTest(unittest.TestCase):
    def test_decision_outcome_is_recorded_on_final_status(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                db_path = get_db_path()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(db_path) as conn:
                    run_migrations(conn)
                    conn.execute(
                        """
                        INSERT INTO decision_logs (
                            id, created_at, decision_type, decision, status, updated_at, risk_score
                        ) VALUES (?,?,?,?,?,?,?)
                        """,
                        ("201", "2026-01-01T00:00:00+00:00", "strategy_action", "RECOMMEND", "recorded", "2026-01-01T00:00:00+00:00", 3.5),
                    )
                    conn.commit()

                store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
                created = store.add(
                    action_type="scale",
                    target_id="launch-1",
                    reasoning="grow",
                    decision_id="201",
                    event_id="ev-201",
                )
                store.set_status(created["id"], "executed")

                with sqlite3.connect(db_path) as conn:
                    row = conn.execute(
                        "SELECT decision_id, strategy_type, was_autonomous, predicted_risk, revenue_generated, outcome FROM decision_outcomes WHERE decision_id = ?",
                        ("201",),
                    ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "201")
                self.assertEqual(row[1], "scale")
                self.assertEqual(int(row[2]), 0)
                self.assertAlmostEqual(float(row[3]), 3.5)
                self.assertEqual(float(row[4]), 0.0)
                self.assertEqual(row[5], "neutral")

    def test_metrics_summary_endpoint_returns_aggregations(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                storage.conn.execute(
                    """
                    INSERT OR REPLACE INTO decision_outcomes (
                        decision_id, strategy_type, was_autonomous, predicted_risk,
                        revenue_generated, outcome, evaluated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("d-1", "scale", 1, 2.0, 10.0, "success", "2026-01-01T00:00:00+00:00"),
                )
                storage.conn.execute(
                    """
                    INSERT OR REPLACE INTO decision_outcomes (
                        decision_id, strategy_type, was_autonomous, predicted_risk,
                        revenue_generated, outcome, evaluated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("d-2", "review", 0, 5.0, 0.0, "neutral", "2026-01-01T01:00:00+00:00"),
                )
                storage.conn.commit()

                server = start_http_server(host="127.0.0.1", port=0, storage=storage, bus=EventBus())
                try:
                    with urlopen(f"http://127.0.0.1:{server.server_port}/metrics/strategic/summary", timeout=3) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()

                self.assertTrue(payload["ok"])
                data = payload["data"]
                self.assertEqual(data["total_decisions"], 2)
                self.assertEqual(data["total_autonomous"], 1)
                self.assertEqual(data["total_manual"], 1)
                self.assertEqual(data["total_revenue"], 10.0)
                self.assertAlmostEqual(data["success_rate"], 0.5)
                self.assertEqual(data["revenue_por_strategy_type"]["scale"], 10.0)


if __name__ == "__main__":
    unittest.main()
