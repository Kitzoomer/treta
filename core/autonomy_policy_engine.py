from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.adaptive_policy_engine import AdaptivePolicyEngine
from core.bus import EventBus
from core.events import Event
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore


class AutonomyPolicyEngine:
    """Deterministic autonomy guardrails for strategy action auto-execution."""

    def __init__(
        self,
        strategy_action_store: StrategyActionStore,
        strategy_action_execution_layer: StrategyActionExecutionLayer,
        mode: str = "manual",
        max_auto_executions_per_24h: int = 3,
        adaptive_policy_engine: AdaptivePolicyEngine | None = None,
        bus: EventBus | None = None,
    ):
        self._strategy_action_store = strategy_action_store
        self._strategy_action_execution_layer = strategy_action_execution_layer
        self._mode = "partial" if mode == "partial" else "manual"
        self._adaptive_policy_engine = adaptive_policy_engine or AdaptivePolicyEngine(
            impact_threshold=6,
            max_auto_executions_per_24h=max_auto_executions_per_24h,
        )
        self._bus = bus or EventBus()


    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _count_auto_executed_last_24h(self) -> int:
        cutoff = self._utcnow() - timedelta(hours=24)
        count = 0
        for item in self._strategy_action_store.list(status="auto_executed"):
            executed_at = self._parse_datetime(str(item.get("executed_at") or ""))
            if executed_at is not None and executed_at >= cutoff:
                count += 1
        return count

    def _eligible_pending_low_risk_actions(self) -> List[Dict[str, Any]]:
        pending = self._strategy_action_store.list(status="pending_confirmation")
        adaptive_status = self._adaptive_policy_engine.adaptive_status()
        impact_threshold = int(adaptive_status["impact_threshold"])
        eligible = [
            item
            for item in pending
            if item.get("risk_level") == "low"
            and int(item.get("expected_impact_score", 0) or 0) >= impact_threshold
        ]
        return sorted(eligible, key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))))

    def apply(self) -> List[Dict[str, Any]]:
        if self._mode != "partial":
            return []

        already_auto_executed = self._count_auto_executed_last_24h()
        adaptive_status = self._adaptive_policy_engine.adaptive_status()
        max_auto_executions = int(adaptive_status["max_auto_executions_per_24h"])
        remaining_budget = max(max_auto_executions - already_auto_executed, 0)
        if remaining_budget <= 0:
            return []

        executed: List[Dict[str, Any]] = []
        for action in self._eligible_pending_low_risk_actions()[:remaining_budget]:
            action_id = str(action.get("id") or "").strip()
            if not action_id:
                continue
            updated = self._strategy_action_execution_layer.execute_action(action_id, status="auto_executed")
            revenue_delta = float(action.get("revenue_delta", 0) or 0)
            self._adaptive_policy_engine.record_action_outcome(revenue_delta=revenue_delta)
            self._bus.push(
                Event(
                    type="AutonomyActionAutoExecuted",
                    payload={"action": updated, "mode": self._mode},
                    source="autonomy_policy_engine",
                )
            )
            executed.append(updated)

        return executed

    def status(self) -> Dict[str, Any]:
        summary = {
            "mode": self._mode,
            "auto_executed_last_24h": self._count_auto_executed_last_24h(),
            "pending_low_risk_actions": len(self._eligible_pending_low_risk_actions()),
        }
        summary.update(self._adaptive_policy_engine.adaptive_status())
        return summary

    def adaptive_status(self) -> Dict[str, Any]:
        return self._adaptive_policy_engine.adaptive_status()
