from __future__ import annotations

from typing import Any, Dict, List

from core.bus import event_bus, EventBus
from core.events import Event


class AutonomyController:
    """Apply autonomy guardrails after decision-engine evaluation."""

    def __init__(
        self,
        risk_tolerance: int = 5,
        auto_execute_money_threshold: int = 7,
        bus: EventBus | None = None,
    ):
        self.risk_tolerance = risk_tolerance
        self.auto_execute_money_threshold = auto_execute_money_threshold
        self.bus = bus or event_bus

    def handle_evaluated_opportunity(self, decision_result: Dict[str, Any]) -> List[Event]:
        decision = decision_result.get("decision")

        if decision == "execute":
            event = Event(
                type="ActionApproved",
                payload=decision_result,
                source="autonomy_controller",
            )
            self.bus.push(event)
            return [event]

        if decision in {"warn", "warn_overload", "discourage"}:
            event = Event(
                type="ActionRequiresConfirmation",
                payload=decision_result,
                source="autonomy_controller",
            )
            self.bus.push(event)
            return [event]

        return []

    def decide(self, opportunity: Dict[str, Any], decision_result: Dict[str, Any]) -> Dict[str, str]:
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


if __name__ == "__main__":
    controller = AutonomyController()
    example_opportunity = {"money": 8, "risk": 2}
    example_decision = {"decision": "execute"}
    print(controller.decide(example_opportunity, example_decision))
