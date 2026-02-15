import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from core.bus import event_bus
from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.ipc_http import start_http_server
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore


class AutonomyPolicyEngineTest(unittest.TestCase):
    def test_partial_mode_auto_executes_eligible_actions_up_to_limit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
            execution_layer = StrategyActionExecutionLayer(strategy_action_store=store)
            engine = AutonomyPolicyEngine(
                strategy_action_store=store,
                strategy_action_execution_layer=execution_layer,
                mode="partial",
            )

            eligible_ids = []
            for idx in range(4):
                action = store.add(
                    action_type="scale",
                    target_id=f"launch-{idx}",
                    reasoning="scale up",
                    status="pending_confirmation",
                    sales=5,
                )
                eligible_ids.append(action["id"])

            store.add(
                action_type="review",
                target_id="launch-review",
                reasoning="manual check",
                status="pending_confirmation",
            )

            executed = engine.apply()

            self.assertEqual(len(executed), 3)
            executed_ids = {item["id"] for item in executed}
            self.assertEqual(executed_ids, set(eligible_ids[:3]))

            auto_executed = store.list(status="auto_executed")
            self.assertEqual(len(auto_executed), 3)
            self.assertTrue(all(item.get("executed_at") for item in auto_executed))

            pending = store.list(status="pending_confirmation")
            pending_ids = {item["id"] for item in pending}
            self.assertIn(eligible_ids[3], pending_ids)

            recent = [event.type for event in event_bus.recent(limit=10)]
            self.assertIn("AutonomyActionAutoExecuted", recent)

    def test_status_counts_last_24_hours_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "strategy_actions.json"
            now = datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc)
            entries = [
                {
                    "id": "action-000001",
                    "type": "scale",
                    "target_id": "launch-1",
                    "reasoning": "a",
                    "status": "auto_executed",
                    "created_at": (now - timedelta(days=2)).isoformat(),
                    "executed_at": (now - timedelta(hours=1)).isoformat(),
                },
                {
                    "id": "action-000002",
                    "type": "scale",
                    "target_id": "launch-2",
                    "reasoning": "b",
                    "status": "auto_executed",
                    "created_at": (now - timedelta(days=2)).isoformat(),
                    "executed_at": (now - timedelta(hours=30)).isoformat(),
                },
                {
                    "id": "action-000003",
                    "type": "scale",
                    "target_id": "launch-3",
                    "reasoning": "c",
                    "status": "pending_confirmation",
                    "created_at": now.isoformat(),
                    "sales": 5,
                },
            ]
            path.write_text(json.dumps(entries), encoding="utf-8")

            store = StrategyActionStore(path=path)
            execution_layer = StrategyActionExecutionLayer(strategy_action_store=store)
            engine = AutonomyPolicyEngine(
                strategy_action_store=store,
                strategy_action_execution_layer=execution_layer,
                mode="partial",
            )
            engine._utcnow = lambda: now

            status = engine.status()

            self.assertEqual(status["mode"], "partial")
            self.assertEqual(status["auto_executed_last_24h"], 1)
            self.assertEqual(status["pending_low_risk_actions"], 1)

    def test_autonomy_status_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
            execution_layer = StrategyActionExecutionLayer(strategy_action_store=store)
            engine = AutonomyPolicyEngine(
                strategy_action_store=store,
                strategy_action_execution_layer=execution_layer,
                mode="manual",
            )

            store.add(
                action_type="scale",
                target_id="launch-1",
                reasoning="scale up",
                status="pending_confirmation",
                sales=5,
            )

            server = start_http_server(
                host="127.0.0.1",
                port=0,
                autonomy_policy_engine=engine,
            )
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/autonomy/status", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(payload["mode"], "manual")
            self.assertEqual(payload["auto_executed_last_24h"], 0)
            self.assertEqual(payload["pending_low_risk_actions"], 1)


if __name__ == "__main__":
    unittest.main()
