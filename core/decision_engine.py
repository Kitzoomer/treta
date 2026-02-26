from __future__ import annotations

import logging
from typing import Any, Dict

from core.storage import Storage


class DecisionEngine:
    """Evaluate opportunities with weighted scoring and hard decision rules."""

    def __init__(self, storage: Storage, risk_tolerance: int = 5, max_daily_hours: int = 5):
        self.risk_tolerance = risk_tolerance
        self.max_daily_hours = max_daily_hours
        self._storage = storage
        self._logger = logging.getLogger("treta.decision")

    def evaluate(
        self,
        opportunity: Dict[str, Any],
        request_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> Dict[str, Any]:
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

        result = {
            "score": float(score),
            "decision": decision,
            "reasoning": reasoning,
        }
        try:
            self._storage.insert_decision_log(
                    engine="DecisionEngine",
                    input_snapshot=opportunity,
                    computed_score=float(score),
                    rules_applied=["risk_tolerance", "energy_guardrail", "score_threshold"],
                    decision=decision,
                    risk_level="high" if risk > self.risk_tolerance else "medium",
                    request_id=request_id,
                    trace_id=trace_id,
                    event_id=event_id,
                    metadata={"reasoning": reasoning},
                )
        except Exception as exc:
            self._logger.exception("Failed to persist decision log", extra={"request_id": request_id, "engine": "DecisionEngine", "error": str(exc)})
        return result
