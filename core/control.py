from dataclasses import dataclass
from typing import Dict, List

from core.events import Event
from core.decision_engine import DecisionEngine
from core.integrations.gumroad_client import GumroadClient
from core.action_planner import ActionPlanner
from core.confirmation_queue import ConfirmationQueue


@dataclass(frozen=True)
class Action:
    type: str
    payload: Dict[str, object]


class Control:
    """Deterministic event -> action mapper (stub-only)."""

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        gumroad_client: GumroadClient | None = None,
        action_planner: ActionPlanner | None = None,
        confirmation_queue: ConfirmationQueue | None = None,
    ):
        self.decision_engine = decision_engine or DecisionEngine()
        self.gumroad_client = gumroad_client
        self.action_planner = action_planner or ActionPlanner()
        self.confirmation_queue = confirmation_queue or ConfirmationQueue()

    def evaluate_opportunity(self, opportunity: Dict[str, object]) -> Dict[str, object]:
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

        if event.type == "GumroadStatsRequested":
            if self.gumroad_client is None:
                return [
                    Action(
                        type="GumroadStatsReady",
                        payload={"products": [], "sales": [], "balance": {}},
                    )
                ]

            products_payload = self.gumroad_client.get_products()
            sales_payload = self.gumroad_client.get_sales()
            balance_payload = self.gumroad_client.get_balance()

            return [
                Action(
                    type="GumroadStatsReady",
                    payload={
                        "products": products_payload.get("products", []),
                        "sales": sales_payload.get("sales", []),
                        "balance": balance_payload,
                    },
                )
            ]

        if event.type == "ActionApproved":
            plan = self.action_planner.plan(event.payload)
            return [Action(type="ActionPlanGenerated", payload=plan)]

        if event.type == "ActionPlanGenerated":
            queued_plan = self.confirmation_queue.add(event.payload)
            return [Action(type="AwaitingConfirmation", payload=queued_plan)]

        if event.type == "ConfirmAction":
            plan_id = str(event.payload.get("plan_id", ""))
            approved = self.confirmation_queue.approve(plan_id)
            if approved is None:
                return []
            return [Action(type="ActionConfirmed", payload=approved)]

        if event.type == "RejectAction":
            plan_id = str(event.payload.get("plan_id", ""))
            rejected = self.confirmation_queue.reject(plan_id)
            if rejected is None:
                return []
            return [Action(type="ActionRejected", payload=rejected)]

        if event.type == "EvaluateOpportunity":
            result = self.evaluate_opportunity(event.payload)
            print(f"[DECISION] score={result['score']:.2f} decision={result['decision']}")
            return [Action(type="OpportunityEvaluated", payload=result)]

        return []
