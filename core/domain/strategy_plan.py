from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4


@dataclass(frozen=True)
class StrategyPlan:
    decision_id: str
    created_at: str
    context_snapshot: Dict[str, Any]
    recommended_actions: List[Dict[str, Any]]
    autonomy_intent: Dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        context_snapshot: Dict[str, Any],
        recommended_actions: List[Dict[str, Any]],
        autonomy_intent: Dict[str, Any],
        decision_id: str | None = None,
        created_at: str | None = None,
    ) -> "StrategyPlan":
        plan_decision_id = str(decision_id or uuid4())
        plan_created_at = created_at or datetime.now(timezone.utc).isoformat()
        return cls(
            decision_id=plan_decision_id,
            created_at=plan_created_at,
            context_snapshot=context_snapshot,
            recommended_actions=recommended_actions,
            autonomy_intent=autonomy_intent,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "created_at": self.created_at,
            "context_snapshot": self.context_snapshot,
            "recommended_actions": self.recommended_actions,
            "autonomy_intent": self.autonomy_intent,
        }
