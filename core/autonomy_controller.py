from __future__ import annotations

from typing import Any, Dict


class AutonomyController:
    """Apply autonomy guardrails after decision-engine evaluation."""

    def __init__(self, risk_tolerance: int = 5, auto_execute_money_threshold: int = 7):
        self.risk_tolerance = risk_tolerance
        self.auto_execute_money_threshold = auto_execute_money_threshold

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
