from __future__ import annotations

from typing import Any, Dict, List

from core.bus import EventBus
from core.events import Event
from core.strategy_action_store import StrategyActionStore


class StrategyActionExecutionLayer:
    """Handles confirmation-gated execution for strategy actions."""

    def __init__(self, strategy_action_store: StrategyActionStore, bus: EventBus):
        self._strategy_action_store = strategy_action_store
        self._bus = bus

    def register_pending_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
                )
            )

        return created

    def list_pending_actions(self) -> List[Dict[str, Any]]:
        return self._strategy_action_store.list(status="pending_confirmation")

    def execute_action(self, action_id: str, status: str = "executed") -> Dict[str, Any]:
        updated = self._strategy_action_store.set_status(action_id, status)
        self._bus.push(
            Event(
                type="StrategyActionExecuted",
                payload={"action": updated},
                source="strategy_action_execution_layer",
            )
        )
        return updated

    def reject_action(self, action_id: str) -> Dict[str, Any]:
        return self._strategy_action_store.set_status(action_id, "rejected")
