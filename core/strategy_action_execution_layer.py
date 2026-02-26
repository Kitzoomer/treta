from __future__ import annotations

from typing import Any, Dict, List

from core.action_execution_store import ActionExecutionStore
from core.bus import EventBus
from core.events import Event
from core.executors.registry import ActionExecutorRegistry
from core.strategy_action_store import StrategyActionStore
from core.storage import Storage


class StrategyActionExecutionLayer:
    def __init__(
        self,
        strategy_action_store: StrategyActionStore,
        bus: EventBus,
        storage: Storage | None = None,
        action_execution_store: ActionExecutionStore | None = None,
        executor_registry: ActionExecutorRegistry | None = None,
    ):
        self._strategy_action_store = strategy_action_store
        self._bus = bus
        self._storage = storage
        self._action_execution_store = action_execution_store
        self._executor_registry = executor_registry

    def register_pending_actions(
        self,
        actions: List[Dict[str, Any]],
        decision_id: str | None = None,
        event_id: str | None = None,
        trace_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        created: List[Dict[str, Any]] = []

        for action in actions:
            action_type = str(action.get("type") or "").strip()
            target_id = str(action.get("target_id") or "").strip()
            reasoning = str(action.get("reasoning") or "").strip()
            sales = action.get("sales")
            if not action_type or not target_id or not reasoning:
                continue

            existing = self._strategy_action_store.find_pending(
                action_type=action_type,
                target_id=target_id,
                reasoning=reasoning,
            )
            if existing is not None:
                continue

            created.append(
                self._strategy_action_store.add(
                    action_type=action_type,
                    target_id=target_id,
                    reasoning=reasoning,
                    status="pending_confirmation",
                    sales=sales,
                    decision_id=decision_id,
                    event_id=event_id,
                    trace_id=trace_id,
                )
            )

        return created

    def list_pending_actions(self) -> List[Dict[str, Any]]:
        return self._strategy_action_store.list(status="pending_confirmation")

    def execute_action(self, action_id: str, status: str = "executed", request_id: str | None = None, trace_id: str | None = None) -> Dict[str, Any]:
        updated = self._strategy_action_store.set_status(action_id, status)
        self._bus.push(
            Event(
                type="StrategyActionExecuted",
                payload={"action": updated},
                source="strategy_action_execution_layer",
                request_id=request_id or "",
                trace_id=trace_id or "",
            )
        )
        self._bus.push(
            Event(
                type="ExecuteStrategyAction",
                payload={
                    "action_id": action_id,
                    "request_id": request_id or str(updated.get("event_id") or ""),
                    "trace_id": trace_id or str(updated.get("trace_id") or ""),
                    "correlation_id": str(updated.get("decision_id") or ""),
                    "strategy_status": status,
                },
                source="strategy_action_execution_layer",
                request_id=request_id or "",
                trace_id=trace_id or "",
            )
        )
        if self._storage is not None:
            self._storage.create_decision_log(
                {
                    "decision_type": "strategy_action",
                    "entity_type": "action",
                    "entity_id": str(updated.get("id") or action_id),
                    "action_type": "execute",
                    "decision": "ALLOW",
                    "inputs_json": {"action_id": action_id, "requested_status": status},
                    "outputs_json": {"action": updated},
                    "reason": "Strategy action status transitioned to executed state.",
                    "status": "executed" if status in {"executed", "auto_executed"} else "recorded",
                }
            )
        return updated

    def reject_action(self, action_id: str) -> Dict[str, Any]:
        updated = self._strategy_action_store.set_status(action_id, "rejected")
        if self._storage is not None:
            self._storage.create_decision_log(
                {
                    "decision_type": "strategy_action",
                    "entity_type": "action",
                    "entity_id": str(updated.get("id") or action_id),
                    "action_type": "skip",
                    "decision": "DENY",
                    "inputs_json": {"action_id": action_id},
                    "outputs_json": {"action": updated},
                    "reason": "Strategy action was rejected by operator.",
                    "status": "skipped",
                }
            )
        return updated
