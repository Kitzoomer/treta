from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CoherenceCheckResult:
    is_coherent: bool
    contradictions: list[str]
    drastic_changes: list[str]
    requires_human_review: bool


class CoherenceCheckEngine:
    """Detects drift/contradictions between a new strategic plan and a known snapshot."""

    def evaluate(self, plan: dict[str, Any], snapshot: str) -> CoherenceCheckResult:
        contradictions: list[str] = []
        drastic_changes: list[str] = []

        objective = str(plan.get("objective") or "").strip().lower()
        steps = plan.get("steps", [])
        snapshot_text = str(snapshot or "").strip().lower()

        if not snapshot_text:
            return CoherenceCheckResult(True, [], [], False)

        if "no" in objective and "sí" in snapshot_text:
            contradictions.append("Objective negates a positive snapshot signal.")

        if "pause" in objective and "urgent" in snapshot_text:
            contradictions.append("Objective asks to pause while snapshot indicates urgency.")

        if isinstance(steps, list) and len(steps) >= 8:
            drastic_changes.append("Plan introduces a high number of steps compared to usual short cycles.")

        snapshot_tokens = {token for token in snapshot_text.split() if len(token) > 3}
        objective_tokens = {token for token in objective.split() if len(token) > 3}
        overlap = len(snapshot_tokens & objective_tokens)

        if objective_tokens and len(snapshot_tokens) >= 6 and overlap == 0 and ("pivot" in objective or "reinvent" in objective):
            drastic_changes.append("Objective has no semantic overlap with snapshot context.")

        incoherent = bool(contradictions or drastic_changes)
        return CoherenceCheckResult(
            is_coherent=not incoherent,
            contradictions=contradictions,
            drastic_changes=drastic_changes,
            requires_human_review=incoherent,
        )
