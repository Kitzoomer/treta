from dataclasses import dataclass
from typing import Any, Dict, List

from core.events import Event
from core.decision_engine import DecisionEngine
from core.autonomy_controller import AutonomyController


@dataclass(frozen=True)
class Action:
    type: str
    payload: Dict[str, Any]


class Control:
    """Deterministic event -> action mapper (stub-only)."""

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        autonomy_controller: AutonomyController | None = None,
    ):
        self.decision_engine = decision_engine or DecisionEngine()
        self.autonomy_controller = autonomy_controller or AutonomyController()
    def __init__(self, decision_engine: DecisionEngine | None = None):
        self.decision_engine = decision_engine or DecisionEngine()

    def evaluate_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        return self.decision_engine.evaluate(opportunity)

    def consume(self, event: Event) -> List[Action]:
        if event.type == "DailyBriefRequested":
            print("[CONTROL] DailyBriefRequested -> would build daily brief summary (stub)")
            return [Action(type="BuildDailyBrief", payload={"dry_run": True})]

        if event.type == "OpportunityScanRequested":
            print("[CONTROL] OpportunityScanRequested -> would run opportunity scan (stub)")
            return [Action(type="RunOpportunityScan", payload={"dry_run": True})]

        if event.type == "EmailTriageRequested":
            print("[CONTROL] EmailTriageRequested -> would triage inbox in dry-run mode (stub)")
            return [Action(type="RunEmailTriage", payload={"dry_run": True})]

        if event.type == "EvaluateOpportunity":
            result = self.evaluate_opportunity(event.payload)
            print(f"[DECISION] score={result['score']:.2f} decision={result['decision']}")
            return [Action(type="OpportunityEvaluated", payload=result)]

        if event.type == "OpportunityEvaluated":
            emitted = self.autonomy_controller.handle_evaluated_opportunity(event.payload)
            return [Action(type=e.type, payload=e.payload) for e in emitted]

        return []
