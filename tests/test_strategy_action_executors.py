import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.action_execution_store import ActionExecutionStore
from core.bus import EventBus
from core.control import Control
from core.dispatcher import Dispatcher
from core.events import Event
from core.executors.draft_asset_executor import DraftAssetExecutor
from core.executors.registry import ActionExecutorRegistry
from core.state_machine import StateMachine
from core.storage import Storage
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore


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


if __name__ == "__main__":
    unittest.main()
