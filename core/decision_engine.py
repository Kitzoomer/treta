from __future__ import annotations

from typing import Any, Dict


class DecisionEngine:
    """Evaluate opportunities with weighted scoring and hard decision rules."""

    def __init__(self, risk_tolerance: int = 5, max_daily_hours: int = 5):
        self.risk_tolerance = risk_tolerance
        self.max_daily_hours = max_daily_hours

    def evaluate(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        money = float(opportunity.get("money", 0))
        growth = float(opportunity.get("growth", 0))
        energy = float(opportunity.get("energy", 0))
        health = float(opportunity.get("health", 0))
        relationships = float(opportunity.get("relationships", 0))
        risk = float(opportunity.get("risk", 0))

        score = (
            (money * 1.8)
            + (growth * 1.2)
            + (relationships * 0.5)
            + (health * 0.5)
            - (energy * 0.8)
            - (risk * 1.7)
        )

        if risk > self.risk_tolerance:
            decision = "reject"
            reasoning = (
                f"Risk ({risk:.2f}) exceeds tolerance ({self.risk_tolerance})."
            )
        elif energy > 8:
            decision = "warn_overload"
            reasoning = f"Energy cost ({energy:.2f}) indicates potential overload."
        elif score < 0:
            decision = "discourage"
            reasoning = f"Composite score is negative ({score:.2f})."
        else:
            decision = "execute"
            reasoning = f"Composite score is favorable ({score:.2f}) within current limits."

        return {
            "score": float(score),
            "decision": decision,
            "reasoning": reasoning,
        }
