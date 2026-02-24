from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List

from core.adaptive_policy_engine import AdaptivePolicyEngine
from core.bus import EventBus
from core.events import Event
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_action_store import StrategyActionStore
from core.storage import Storage


class AutonomyPolicyEngine:
    """Deterministic autonomy guardrails for strategy action auto-execution."""

    def __init__(
        self,
        strategy_action_store: StrategyActionStore,
        strategy_action_execution_layer: StrategyActionExecutionLayer,
        storage: Storage,
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
        self._storage = storage
        self._logger = logging.getLogger("treta.autonomy")


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

    def apply(self, request_id: str | None = None) -> List[Dict[str, Any]]:
        if self._mode != "partial":
            try:
                self._storage.create_decision_log(
                    {
                        "decision_type": "autonomy",
                        "decision": "MANUAL",
                        "policy_name": "AutonomyPolicyEngine",
                        "policy_snapshot_json": {"mode": self._mode},
                        "reason": "Autonomy mode is manual; no auto execution.",
                        "correlation_id": request_id,
                        "status": "skipped",
                    }
                )
            except Exception:
                pass
            return []

        already_auto_executed = self._count_auto_executed_last_24h()
        adaptive_status = self._adaptive_policy_engine.adaptive_status()
        max_auto_executions = int(adaptive_status["max_auto_executions_per_24h"])
        remaining_budget = max(max_auto_executions - already_auto_executed, 0)
        if remaining_budget <= 0:
            try:
                self._storage.create_decision_log(
                    {
                        "decision_type": "autonomy",
                        "decision": "DENY",
                        "policy_name": "AutonomyPolicyEngine",
                        "policy_snapshot_json": adaptive_status,
                        "reason": "No remaining autonomy budget in the last 24h.",
                        "correlation_id": request_id,
                        "status": "skipped",
                    }
                )
            except Exception:
                pass
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
                    payload={"action": updated, "mode": self._mode, "request_id": request_id},
                    source="autonomy_policy_engine",
                    request_id=request_id or "",
                )
            )
            try:
                adaptive = self._adaptive_policy_engine.adaptive_status()
                self._storage.create_decision_log(
                    {
                        "decision_type": "autonomy",
                        "entity_type": "action",
                        "entity_id": action_id,
                        "action_type": "execute",
                        "decision": "ALLOW",
                        "risk_score": float(action.get("expected_impact_score", 0) or 0),
                        "autonomy_score": float(action.get("expected_impact_score", 0) or 0),
                        "policy_name": "AutonomyPolicyEngine",
                        "policy_snapshot_json": {
                            "mode": self._mode,
                            "impact_threshold": adaptive.get("impact_threshold"),
                            "max_auto_executions_per_24h": adaptive.get("max_auto_executions_per_24h"),
                        },
                        "inputs_json": {
                            "action_id": action_id,
                            "risk_level": action.get("risk_level"),
                            "expected_impact_score": action.get("expected_impact_score"),
                        },
                        "outputs_json": {"action": updated},
                        "reason": "Eligible low-risk action auto-executed within adaptive budget.",
                        "correlation_id": request_id,
                        "status": "executed",
                    }
                )
            except Exception as exc:
                self._logger.exception("Failed to persist autonomy decision log", extra={"request_id": request_id, "error": str(exc)})
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
