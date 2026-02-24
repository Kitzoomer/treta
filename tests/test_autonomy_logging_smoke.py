from __future__ import annotations

import os
import tempfile

from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.bus import EventBus
from core.storage import Storage
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore


def test_autonomy_logging_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        old = os.environ.get("TRETA_DATA_DIR")
        os.environ["TRETA_DATA_DIR"] = tmp_dir
        try:
            storage = Storage()
            action_store = StrategyActionStore()
            bus = EventBus()
            execution = StrategyActionExecutionLayer(strategy_action_store=action_store, bus=bus, storage=storage)
            action_store.add(
                action_type="scale",
                target_id="launch-1",
                reasoning="high signal",
                status="pending_confirmation",
                sales=10,
            )
            engine = AutonomyPolicyEngine(
                strategy_action_store=action_store,
                strategy_action_execution_layer=execution,
                storage=storage,
                mode="partial",
                max_auto_executions_per_24h=1,
                bus=bus,
            )

            engine.apply(request_id="autonomy-smoke-1")
            items = storage.list_recent_decision_logs(limit=20, decision_type="autonomy")
            assert any(item.get("decision") in {"ALLOW", "DENY", "MANUAL"} for item in items)
        finally:
            if old is None:
                os.environ.pop("TRETA_DATA_DIR", None)
            else:
                os.environ["TRETA_DATA_DIR"] = old
