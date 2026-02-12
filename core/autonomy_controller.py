from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.bus import EventBus, event_bus
from core.events import Event


class AutonomyController:
    """Post-decision autonomy executor for evaluated opportunities.

    - Backward-compatible guardrail API via `decide(...)`.
    - Event-driven autonomy loop via `handle_evaluated_opportunity(...)`.
    """

    def __init__(
        self,
        risk_tolerance: int = 5,
        auto_execute_money_threshold: int = 7,
        bus: Optional[EventBus] = None,
    ):
        self.risk_tolerance = risk_tolerance
        self.auto_execute_money_threshold = auto_execute_money_threshold
        self.bus = bus or event_bus

    def decide(self, opportunity: Dict[str, Any], decision_result: Dict[str, Any]) -> Dict[str, str]:
        """Backward-compatible policy gate used by prior tests/integration points."""
        if decision_result["decision"] == "reject":
            return {"action": "block", "reason": "decision_engine_rejected"}

        if opportunity["risk"] > self.risk_tolerance:
            return {"action": "block", "reason": "risk_above_tolerance"}

        if (
            opportunity["money"] >= self.auto_execute_money_threshold
            and opportunity["risk"] <= 3
        ):
            return {"action": "auto_execute", "reason": "high_value_low_risk"}

        return {"action": "ask_user", "reason": "manual_confirmation_required"}

    def handle_evaluated_opportunity(self, result: Dict[str, Any]) -> List[Event]:
        """Emit autonomy events from structured DecisionEngine evaluation output."""
        decision = str(result.get("decision", "")).strip()
        score = float(result.get("score", 0.0))

        if decision == "execute":
            event = Event(
                type="ActionApproved",
                payload={
                    "score": score,
                    "decision": decision,
                    "reasoning": result.get("reasoning", ""),
                },
                source="autonomy_controller",
            )
            self.bus.push(event)
            print(f"[AUTONOMY] executing action score={score:.2f}")
            return [event]

        if decision in {"warn", "warn_overload"}:
            event = Event(
                type="ActionRequiresConfirmation",
                payload={
                    "score": score,
                    "decision": decision,
                    "reasoning": result.get("reasoning", ""),
                },
                source="autonomy_controller",
            )
            self.bus.push(event)
            print("[AUTONOMY] warning - confirmation required")
            return [event]

        if decision in {"reject", "discourage"}:
            print("[AUTONOMY] rejected opportunity")

        return []
