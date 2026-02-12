from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.bus import EventBus, event_bus
from core.events import Event


class AutonomyController:
    """Post-decision autonomy executor for evaluated opportunities.

    Consumes structured DecisionEngine outcomes and emits follow-up events
    for downstream control/dispatcher flow.
    """

    def __init__(self, bus: Optional[EventBus] = None):
        self.bus = bus or event_bus

    def handle_evaluated_opportunity(self, result: Dict[str, Any]) -> List[Event]:
        decision = str(result.get("decision", "")).strip()
        score = float(result.get("score", 0.0))

        if decision == "execute":
            event = Event(
                type="ActionApproved",
                payload={"score": score, "decision": decision, "reasoning": result.get("reasoning", "")},
                source="autonomy_controller",
            )
            self.bus.push(event)
            print(f"[AUTONOMY] executing action score={score:.2f}")
            return [event]

        if decision in {"warn", "warn_overload"}:
            event = Event(
                type="ActionRequiresConfirmation",
                payload={"score": score, "decision": decision, "reasoning": result.get("reasoning", "")},
                source="autonomy_controller",
            )
            self.bus.push(event)
            print("[AUTONOMY] warning – confirmation required")
            return [event]

        if decision in {"reject", "discourage"}:
            print("[AUTONOMY] rejected opportunity")

        return []
