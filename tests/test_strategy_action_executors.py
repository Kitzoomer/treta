import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.action_execution_store import ActionExecutionStore
from core.bus import EventBus
from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.executors.draft_asset_executor import DraftAssetExecutor
from core.executors.registry import ActionExecutorRegistry
from core.handlers.strategy_handler import StrategyHandler
from core.state_machine import StateMachine
from core.storage import Storage
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore


class CountingExecutor:
    name = "counting"
    supported_types = ["draft_asset"]

    def __init__(self):
        self.calls = 0

    def execute(self, action, context):
        self.calls += 1
        return {"ok": True, "action_id": action.get("id")}


class StrategyExecutorFlowTest(unittest.TestCase):
    def test_execute_strategy_action_event_runs_draft_asset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                bus = EventBus()
                store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
                exec_store = ActionExecutionStore(storage.conn)
                registry = ActionExecutorRegistry()
                registry.register(DraftAssetExecutor())
                layer = StrategyActionExecutionLayer(
                    strategy_action_store=store,
                    bus=bus,
                    storage=storage,
                    action_execution_store=exec_store,
                    executor_registry=registry,
                )
                control = Control(bus=bus, strategy_action_execution_layer=layer)
                dispatcher = Dispatcher(state_machine=StateMachine(), control=control, bus=bus, storage=storage)

                created = layer.register_pending_actions(
                    [{"type": "draft_asset", "target_id": "launch-1", "reasoning": "Crear copy base"}],
                    decision_id="d1",
                    event_id="ev1",
                    trace_id="tr1",
                )
                action_id = created[0]["id"]
                layer.execute_action(action_id)

                while True:
                    ev = bus.pop(timeout=0.05)
                    if ev is None:
                        break
                    dispatcher.handle(ev)

                executions = exec_store.list_for_action(action_id)
                self.assertGreaterEqual(len(executions), 1)
                self.assertEqual(executions[0]["status"], "success")
                self.assertIn("Borrador", executions[0]["output_payload_json"])

                updated = store.get(action_id)
                self.assertEqual(updated["status"], "executed")

                before = len(exec_store.list_for_action(action_id))
                dispatcher.handle(
                    Event(type="ExecuteStrategyAction", payload={"action_id": action_id}, source="test")
                )
                after = len(exec_store.list_for_action(action_id))
                self.assertEqual(before, after)


    def test_running_execution_blocks_duplicate_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                bus = EventBus()
                store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
                exec_store = ActionExecutionStore(storage.conn)
                registry = ActionExecutorRegistry()
                executor = CountingExecutor()
                registry.register(executor)

                action = store.add(
                    action_type="draft_asset",
                    target_id="launch-2",
                    reasoning="Crear copy base",
                    status="pending_confirmation",
                )
                execution_id = exec_store.create_queued(
                    action_id=action["id"],
                    action_type="draft_asset",
                    executor=executor.name,
                    context={},
                )
                exec_store.mark_running(execution_id)

                emitted = StrategyHandler._execute_strategy_action(
                    Event(type="ExecuteStrategyAction", payload={"action_id": action["id"]}, source="test"),
                    {
                        "Action": Event,
                        "strategy_action_execution_layer": type("Layer", (), {
                            "_strategy_action_store": store,
                            "_action_execution_store": exec_store,
                            "_executor_registry": registry,
                        })(),
                        "storage": storage,
                    },
                )

                self.assertEqual(executor.calls, 0)
                self.assertEqual(len(emitted), 1)
                self.assertEqual(emitted[0].type, "StrategyActionExecutionSkipped")
                self.assertEqual(emitted[0].payload.get("reason"), "execution_already_in_progress")

    def test_running_execution_timeout_allows_recovery(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                bus = EventBus()
                store = StrategyActionStore(path=Path(tmp_dir) / "strategy_actions.json")
                exec_store = ActionExecutionStore(storage.conn)
                registry = ActionExecutorRegistry()
                executor = CountingExecutor()
                registry.register(executor)

                action = store.add(
                    action_type="draft_asset",
                    target_id="launch-3",
                    reasoning="Crear copy base",
                    status="pending_confirmation",
                )
                execution_id = exec_store.create_queued(
                    action_id=action["id"],
                    action_type="draft_asset",
                    executor=executor.name,
                    context={},
                )
                exec_store.mark_running(execution_id)

                stale_started_at = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()
                storage.conn.execute(
                    "UPDATE action_executions SET started_at = ? WHERE id = ?",
                    (stale_started_at, execution_id),
                )
                storage.conn.commit()

                emitted = StrategyHandler._execute_strategy_action(
                    Event(type="ExecuteStrategyAction", payload={"action_id": action["id"]}, source="test"),
                    {
                        "Action": Event,
                        "strategy_action_execution_layer": type("Layer", (), {
                            "_strategy_action_store": store,
                            "_action_execution_store": exec_store,
                            "_executor_registry": registry,
                        })(),
                        "storage": storage,
                    },
                )

                self.assertEqual(executor.calls, 1)
                self.assertEqual(len(emitted), 1)
                self.assertEqual(emitted[0].type, "StrategyActionExecuted")
                executions = exec_store.list_for_action(action["id"], limit=10)
                statuses = [item["status"] for item in executions]
                self.assertIn("failed_timeout", statuses)
                self.assertEqual(executions[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
