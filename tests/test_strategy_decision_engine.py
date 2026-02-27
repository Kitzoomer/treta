import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.bus import EventBus
from core.control import Control
from core.decision_engine import DecisionEngine
import core.ipc_http as ipc_http
from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.services.strategy_decision_orchestrator import StrategyDecisionOrchestrator
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore
from core.strategy_decision_engine import StrategyDecisionEngine
from core.storage import Storage


class _FakeAutonomyPolicyEngine:
    def __init__(self):
        self.apply_calls = 0

    def apply(self, request_id=None):
        self.apply_calls += 1
        return []


class StrategyDecisionEngineTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self._prev_strategy_loop_enabled_env = os.environ.get("STRATEGY_LOOP_ENABLED")
        os.environ["STRATEGY_LOOP_ENABLED"] = "false"
        self._prev_strategy_loop_enabled_flag = ipc_http.STRATEGY_LOOP_ENABLED
        ipc_http.STRATEGY_LOOP_ENABLED = False

    def tearDown(self):
        if self._prev_strategy_loop_enabled_env is None:
            os.environ.pop("STRATEGY_LOOP_ENABLED", None)
        else:
            os.environ["STRATEGY_LOOP_ENABLED"] = self._prev_strategy_loop_enabled_env
        ipc_http.STRATEGY_LOOP_ENABLED = self._prev_strategy_loop_enabled_flag

    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def test_strategy_decide_is_pure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(product_launch_store=launches)
            plan = engine.decide()

            self.assertIsInstance(plan.decision_id, str)
            self.assertIn("scale", [item["type"] for item in plan.recommended_actions])
            self.assertEqual(plan.autonomy_intent["should_execute"], True)

    def test_orchestrator_materializes_actions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            os.environ["TRETA_DATA_DIR"] = str(root / ".treta_data")
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)
            storage = Storage()
            orchestrator = StrategyDecisionOrchestrator(
                engine=StrategyDecisionEngine(product_launch_store=launches),
                storage=storage,
                strategy_action_execution_layer=layer,
                autonomy_policy_engine=_FakeAutonomyPolicyEngine(),
            )

            result = orchestrator.run_decision_cycle(request_id="r1", trace_id="t1", event_id="e1")
            pending = layer.list_pending_actions()
            self.assertEqual(result["status"], "executed")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["type"], "scale")

    def test_orchestrator_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            os.environ["TRETA_DATA_DIR"] = str(root / ".treta_data")
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)
            storage = Storage()
            orchestrator = StrategyDecisionOrchestrator(
                engine=StrategyDecisionEngine(product_launch_store=launches, decision_id_factory=lambda: "fixed-decision"),
                storage=storage,
                strategy_action_execution_layer=layer,
                autonomy_policy_engine=_FakeAutonomyPolicyEngine(),
            )

            first = orchestrator.run_decision_cycle()
            second = orchestrator.run_decision_cycle()
            pending = layer.list_pending_actions()
            self.assertEqual(first["status"], "executed")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(len(pending), 1)

    def test_autonomy_called_only_in_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            fake_autonomy = _FakeAutonomyPolicyEngine()
            engine = StrategyDecisionEngine(product_launch_store=launches)
            engine.decide()
            self.assertEqual(fake_autonomy.apply_calls, 0)

            os.environ["TRETA_DATA_DIR"] = str(root / ".treta_data")
            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)
            orchestrator = StrategyDecisionOrchestrator(
                engine=engine,
                storage=Storage(),
                strategy_action_execution_layer=layer,
                autonomy_policy_engine=fake_autonomy,
            )
            orchestrator.run_decision_cycle(request_id="req-1")
            self.assertEqual(fake_autonomy.apply_calls, 1)

    def test_strategy_decide_endpoint_skips_when_cycle_lock_is_active(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            os.environ["TRETA_DATA_DIR"] = str(root / ".treta_data")
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            storage = Storage()
            action_store = StrategyActionStore(path=root / "strategy_actions.json")
            layer = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=self.bus)
            orchestrator = StrategyDecisionOrchestrator(
                engine=StrategyDecisionEngine(product_launch_store=launches),
                storage=storage,
                strategy_action_execution_layer=layer,
                autonomy_policy_engine=_FakeAutonomyPolicyEngine(),
            )
            control = Control(
                opportunity_store=None,
                product_proposal_store=proposals,
                product_plan_store=None,
                product_launch_store=launches,
                strategy_decision_engine=orchestrator._engine,
                strategy_decision_orchestrator=orchestrator,
                bus=self.bus,
                decision_engine=DecisionEngine(storage=storage),
            )

            original_consume = control.consume
            first_started = threading.Event()
            release_first = threading.Event()
            first_call_lock = threading.Lock()
            first_call_seen = {"value": False}

            def blocking_consume(event):
                with first_call_lock:
                    is_first = not first_call_seen["value"]
                    if is_first:
                        first_call_seen["value"] = True
                if is_first:
                    first_started.set()
                    release_first.wait(timeout=2)
                return original_consume(event)

            control.consume = blocking_consume

            server = start_http_server(host="127.0.0.1", port=0, strategy_decision_engine=orchestrator._engine, strategy_decision_orchestrator=orchestrator, control=control, storage=storage, bus=self.bus)
            try:
                port = server.server_port
                first_response_payload = {}

                def first_request():
                    with urlopen(f"http://127.0.0.1:{port}/strategy/decide", timeout=3) as response:
                        first_response_payload["payload"] = json.loads(response.read().decode("utf-8"))

                first_thread = threading.Thread(target=first_request)
                first_thread.start()
                self.assertTrue(first_started.wait(timeout=1.5))

                with urlopen(f"http://127.0.0.1:{port}/strategy/decide", timeout=3) as second_response:
                    second_payload = json.loads(second_response.read().decode("utf-8"))

                release_first.set()
                first_thread.join(timeout=2)
                self.assertFalse(first_thread.is_alive())
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(first_response_payload["payload"]["data"]["status"], "executed")
            self.assertEqual(second_payload["data"]["status"], "skipped")
            self.assertEqual(second_payload["data"]["reason"], "cycle_lock_active")


if __name__ == "__main__":
    unittest.main()
