import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from core.bus import EventBus
from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore
from core.strategy_decision_engine import StrategyDecisionEngine
from core.storage import Storage


class StrategyDecisionEngineTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def test_rule_scale_when_sales_at_least_five(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")

            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            decision = StrategyDecisionEngine(product_launch_store=launches, storage=Storage()).decide()

            self.assertIn(
                {
                    "type": "scale",
                    "target_id": launch["id"],
                    "sales": 5,
                    "reasoning": "Launch has 5 sales, which meets the scale threshold.",
                },
                decision["actions"],
            )

    def test_rule_review_when_zero_sales_after_seven_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")

            items = json.loads((root / "product_launches.json").read_text(encoding="utf-8"))
            items[0]["created_at"] = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
            (root / "product_launches.json").write_text(json.dumps(items), encoding="utf-8")

            launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
            engine = StrategyDecisionEngine(product_launch_store=launches, storage=Storage())
            engine._utcnow = lambda: datetime(2025, 1, 10, tzinfo=timezone.utc)

            decision = engine.decide()

            self.assertIn(
                {
                    "type": "review",
                    "target_id": launch["id"],
                    "reasoning": "Launch has 0 sales after 9 days.",
                },
                decision["actions"],
            )

    def test_rule_price_test_when_high_revenue_per_sale_and_low_sales(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            launches.add_sale(launch["id"], 100)

            decision = StrategyDecisionEngine(product_launch_store=launches, storage=Storage()).decide()

            self.assertIn(
                {
                    "type": "price_test",
                    "target_id": launch["id"],
                    "reasoning": "Revenue per sale is 100.00 with only 1 total sales.",
                },
                decision["actions"],
            )

    def test_rule_new_product_when_no_active_launches(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)

            decision = StrategyDecisionEngine(product_launch_store=launches, storage=Storage()).decide()

            self.assertIn(
                {
                    "type": "new_product",
                    "target_id": "portfolio",
                    "reasoning": "No active launches were found.",
                },
                decision["actions"],
            )

    def test_decide_uses_adaptive_prioritization_when_available(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            launches.add_sale(launch["id"], 100)

            class FakeAutonomyPolicyEngine:
                def prioritize_strategy_actions(self, actions):
                    return sorted(actions, key=lambda item: 0 if item.get("type") == "price_test" else 1)

                def apply(self, request_id=None):
                    return []

            engine = StrategyDecisionEngine(
                product_launch_store=launches,
                storage=Storage(),
                autonomy_policy_engine=FakeAutonomyPolicyEngine(),
            )

            decision = engine.decide()
            self.assertGreaterEqual(len(decision["actions"]), 1)
            self.assertEqual(decision["actions"][0]["type"], "price_test")

    def test_decide_creates_pending_strategy_actions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            action_execution_layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)

            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(
                product_launch_store=launches,
                strategy_action_execution_layer=action_execution_layer,
                storage=Storage(),
            )

            engine.decide()
            pending = action_execution_layer.list_pending_actions()

            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["type"], "scale")
            self.assertEqual(pending[0]["status"], "pending_confirmation")
            self.assertEqual(pending[0]["risk_level"], "low")
            self.assertEqual(pending[0]["expected_impact_score"], 8)
            self.assertTrue(pending[0]["auto_executable"])


    def test_decide_propagates_explicit_event_id_without_request_id_parsing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            action_execution_layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)

            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(
                product_launch_store=launches,
                strategy_action_execution_layer=action_execution_layer,
                storage=Storage(),
            )

            weird_request = "req-without-event-fragment"
            result = engine.decide(request_id=weird_request, trace_id="trace-xyz", event_id="event-xyz")
            self.assertIn("actions", result)

            pending = action_execution_layer.list_pending_actions()
            self.assertGreaterEqual(len(pending), 1)
            self.assertEqual(pending[0].get("event_id"), "event-xyz")
            self.assertEqual(pending[0].get("trace_id"), "trace-xyz")

    def test_strategy_action_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            action_execution_layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)

            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(
                product_launch_store=launches,
                strategy_action_execution_layer=action_execution_layer,
                storage=Storage(),
            )
            engine.decide()

            server = start_http_server(
                host="127.0.0.1",
                port=0,
                strategy_decision_engine=engine,
                bus=self.bus,
                strategy_action_execution_layer=action_execution_layer,
                storage=Storage(),
            )
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/strategy/pending_actions", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    pending_payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(pending_payload["ok"])
                action_id = pending_payload["data"]["items"][0]["id"]
                self.assertEqual(pending_payload["data"]["items"][0]["risk_level"], "low")
                self.assertEqual(pending_payload["data"]["items"][0]["expected_impact_score"], 8)
                self.assertTrue(pending_payload["data"]["items"][0]["auto_executable"])
                execute_request = Request(
                    f"http://127.0.0.1:{port}/strategy/execute_action/{action_id}",
                    data=b"{}",
                    method="POST",
                )
                with urlopen(execute_request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    executed = json.loads(response.read().decode("utf-8"))

                reject_action = action_store.add(
                    action_type="review",
                    target_id="launch-x",
                    reasoning="Manual review needed",
                    status="pending_confirmation",
                )
                reject_request = Request(
                    f"http://127.0.0.1:{port}/strategy/reject_action/{reject_action['id']}",
                    data=b"{}",
                    method="POST",
                )
                with urlopen(reject_request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    rejected = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertTrue(executed["ok"])
            self.assertEqual(executed["data"]["status"], "executed")
            self.assertTrue(rejected["ok"])
            self.assertEqual(rejected["data"]["status"], "rejected")
            recent_events = self.bus.recent(limit=1)
            self.assertEqual(recent_events[-1].type, "StrategyActionExecuted")

    def test_strategy_decide_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(product_launch_store=launches, storage=Storage())
            server = start_http_server(host="127.0.0.1", port=0, strategy_decision_engine=engine, bus=self.bus)
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/strategy/decide", timeout=2) as response:
                    self.assertEqual(response.status, 202)
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"].get("status"), "accepted")
            self.assertEqual(payload["data"].get("message"), "Strategy decision queued")
            recent_events = self.bus.recent(limit=1)
            self.assertEqual(recent_events[-1].type, "RunStrategyDecision")


if __name__ == "__main__":
    unittest.main()
