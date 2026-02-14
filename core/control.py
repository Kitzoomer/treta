from dataclasses import dataclass
from typing import Dict, List

from core.events import Event
from core.decision_engine import DecisionEngine
from core.integrations.gumroad_client import GumroadClient
from core.action_planner import ActionPlanner
from core.confirmation_queue import ConfirmationQueue
from core.opportunity_store import OpportunityStore
from core.bus import event_bus
from core.opportunity_sources.infoproduct_signals import InfoproductSignals
from core.product_engine import ProductEngine
from core.product_proposal_store import ProductProposalStore
from core.product_builder import ProductBuilder
from core.product_plan_store import ProductPlanStore
from core.execution_engine import ExecutionEngine
from core.product_launch_store import ProductLaunchStore


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
        opportunity_store: OpportunityStore | None = None,
        product_engine: ProductEngine | None = None,
        product_proposal_store: ProductProposalStore | None = None,
        product_builder: ProductBuilder | None = None,
        product_plan_store: ProductPlanStore | None = None,
        execution_engine: ExecutionEngine | None = None,
        product_launch_store: ProductLaunchStore | None = None,
    ):
        self.decision_engine = decision_engine or DecisionEngine()
        self.gumroad_client = gumroad_client
        self.action_planner = action_planner or ActionPlanner()
        self.confirmation_queue = confirmation_queue or ConfirmationQueue()
        self.opportunity_store = opportunity_store or OpportunityStore()
        self.product_engine = product_engine or ProductEngine()
        self.product_proposal_store = product_proposal_store or ProductProposalStore()
        self.product_builder = product_builder or ProductBuilder()
        self.product_plan_store = product_plan_store or ProductPlanStore()
        self.execution_engine = execution_engine or ExecutionEngine()
        self.product_launch_store = product_launch_store or ProductLaunchStore(
            proposal_store=self.product_proposal_store,
        )

    def evaluate_opportunity(self, opportunity: Dict[str, object]) -> Dict[str, object]:
        return self.decision_engine.evaluate(opportunity)

    def consume(self, event: Event) -> List[Action]:
        if event.type == "DailyBriefRequested":
            print("[CONTROL] DailyBriefRequested -> would build daily brief summary (stub)")
            return [Action(type="BuildDailyBrief", payload={"dry_run": True})]

        if event.type == "OpportunityScanRequested":
            print("[CONTROL] OpportunityScanRequested -> would run opportunity scan (stub)")
            return [Action(type="RunOpportunityScan", payload={"dry_run": True})]

        if event.type == "RunInfoproductScan":
            scanner = InfoproductSignals()
            scanner.emit_signals(event_bus)
            return []

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
            plan_id = self.confirmation_queue.add(event.payload)
            return [
                Action(
                    type="AwaitingConfirmation",
                    payload={"plan_id": plan_id, "plan": event.payload},
                )
            ]

        if event.type == "ListPendingConfirmations":
            pending = self.confirmation_queue.list_pending()
            return [Action(type="PendingConfirmationsListed", payload={"items": pending})]

        if event.type == "ConfirmAction":
            plan_id = str(event.payload.get("plan_id", ""))
            approved = self.confirmation_queue.approve(plan_id)
            if approved is None:
                return []
            return [
                Action(
                    type="ActionConfirmed",
                    payload={"plan_id": approved["id"], "plan": approved["plan"]},
                )
            ]

        if event.type == "RejectAction":
            plan_id = str(event.payload.get("plan_id", ""))
            rejected = self.confirmation_queue.reject(plan_id)
            if rejected is None:
                return []
            return [
                Action(
                    type="ActionRejected",
                    payload={"plan_id": rejected["id"], "plan": rejected["plan"]},
                )
            ]


        if event.type == "OpportunityDetected":
            created = self.opportunity_store.add(
                item_id=str(event.payload.get("id", "")).strip() or None,
                source=str(event.payload.get("source", "unknown")),
                title=str(event.payload.get("title", "")),
                summary=str(event.payload.get("summary", "")),
                opportunity=dict(event.payload.get("opportunity", {})),
            )
            proposal = self.product_engine.generate(created)
            self.product_proposal_store.add(proposal)
            return [
                Action(
                    type="ProductProposalGenerated",
                    payload={"proposal_id": proposal["id"], "proposal": proposal},
                )
            ]

        if event.type == "ListProductProposals":
            items = self.product_proposal_store.list()
            return [Action(type="ProductProposalsListed", payload={"items": items})]

        if event.type == "GetProductProposalById":
            proposal_id = str(event.payload.get("id", ""))
            item = self.product_proposal_store.get(proposal_id)
            if item is None:
                return []
            return [Action(type="ProductProposalFetched", payload={"item": item})]

        proposal_transitions = {
            "ApproveProposal": "approved",
            "RejectProposal": "rejected",
            "StartBuildingProposal": "building",
            "MarkReadyToLaunch": "ready_to_launch",
            "MarkProposalLaunched": "launched",
            "ArchiveProposal": "archived",
        }
        if event.type in proposal_transitions:
            proposal_id = str(event.payload.get("proposal_id", "")).strip()
            if not proposal_id:
                return []
            updated = self.product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status=proposal_transitions[event.type],
            )
            actions = [
                Action(
                    type="ProductProposalStatusChanged",
                    payload={"proposal_id": updated["id"], "status": updated["status"], "proposal": updated},
                )
            ]
            if event.type == "MarkProposalLaunched":
                launch = self.product_launch_store.add_from_proposal(updated["id"])
                launch = self.product_launch_store.mark_launched(launch["id"])
                actions.append(
                    Action(
                        type="ProductLaunched",
                        payload={
                            "launch_id": launch["id"],
                            "proposal_id": updated["id"],
                        },
                    )
                )
            return actions

        if event.type == "ListProductLaunchesRequested":
            items = self.product_launch_store.list()
            return [Action(type="ProductLaunchesListed", payload={"items": items})]

        if event.type == "GetProductLaunchRequested":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            launch = self.product_launch_store.get(launch_id)
            if launch is None:
                return []
            return [Action(type="ProductLaunchReturned", payload={"launch": launch})]

        if event.type == "AddProductLaunchSale":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            amount = float(event.payload.get("amount", 0))
            updated = self.product_launch_store.add_sale(launch_id, amount)
            return [Action(type="ProductLaunchUpdated", payload={"launch": updated})]

        if event.type == "TransitionProductLaunchStatus":
            launch_id = str(event.payload.get("launch_id", "")).strip()
            status = str(event.payload.get("status", "")).strip()
            updated = self.product_launch_store.transition_status(launch_id, status)
            return [Action(type="ProductLaunchUpdated", payload={"launch": updated})]

        if event.type == "BuildProductPlanRequested":
            proposal_id = str(event.payload.get("proposal_id", ""))
            proposal = self.product_proposal_store.get(proposal_id)
            if proposal is None:
                return []

            existing = self.product_plan_store.get_by_proposal_id(proposal_id)
            if existing is not None:
                return [
                    Action(
                        type="ProductPlanBuilt",
                        payload={
                            "plan_id": existing["plan_id"],
                            "proposal_id": proposal_id,
                            "plan": existing,
                        },
                    )
                ]

            plan = self.product_builder.build(proposal)
            stored = self.product_plan_store.add(plan)
            return [
                Action(
                    type="ProductPlanBuilt",
                    payload={
                        "plan_id": stored["plan_id"],
                        "proposal_id": stored["proposal_id"],
                        "plan": stored,
                    },
                )
            ]

        if event.type == "ListProductPlansRequested":
            items = self.product_plan_store.list()
            return [Action(type="ProductPlansListed", payload={"items": items})]

        if event.type == "GetProductPlanRequested":
            plan_id = str(event.payload.get("plan_id", ""))
            plan = self.product_plan_store.get(plan_id)
            if plan is None:
                return []
            return [Action(type="ProductPlanReturned", payload={"plan": plan})]

        if event.type == "ExecuteProductPlanRequested":
            proposal_id = str(event.payload.get("proposal_id", ""))
            proposal = self.product_proposal_store.get(proposal_id)
            if proposal is None:
                return []

            execution_package = self.execution_engine.generate_execution_package(proposal)
            print(f"[EXECUTION] proposal_id={proposal_id}")
            actions = [
                Action(
                    type="ProductPlanExecuted",
                    payload={
                        "proposal_id": proposal_id,
                        "execution_package": execution_package,
                    },
                )
            ]

            updated = self.product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status="ready_for_review",
            )
            actions.append(
                Action(
                    type="ProductProposalStatusChanged",
                    payload={"proposal_id": updated["id"], "status": updated["status"], "proposal": updated},
                )
            )
            return actions

        if event.type == "ListOpportunities":
            status = event.payload.get("status")
            items = self.opportunity_store.list(status=str(status) if status else None)
            return [Action(type="OpportunitiesListed", payload={"items": items})]

        if event.type == "EvaluateOpportunityById":
            item_id = str(event.payload.get("id", ""))
            target = self.opportunity_store.get(item_id)
            if target is None:
                return []

            result = self.evaluate_opportunity(target["opportunity"])
            updated = self.opportunity_store.set_decision(item_id, result)
            if updated is None:
                return []

            return [
                Action(
                    type="OpportunityEvaluated",
                    payload={"id": item_id, "decision": result, "item": updated},
                )
            ]

        if event.type == "OpportunityDismissed":
            item_id = str(event.payload.get("id", ""))
            updated = self.opportunity_store.set_status(item_id, "dismissed")
            if updated is None:
                return []
            return []

        if event.type == "EvaluateOpportunity":
            result = self.evaluate_opportunity(event.payload)
            print(f"[DECISION] score={result['score']:.2f} decision={result['decision']}")
            return [Action(type="OpportunityEvaluated", payload=result)]

        return []
