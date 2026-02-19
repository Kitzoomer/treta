from dataclasses import dataclass
import tempfile
from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List

from core.events import Event
from core.decision_engine import DecisionEngine
from core.integrations.gumroad_client import GumroadClient
from core.action_planner import ActionPlanner
from core.confirmation_queue import ConfirmationQueue
from core.opportunity_store import OpportunityStore
from core.bus import EventBus
from core.product_engine import ProductEngine
from core.alignment_engine import AlignmentEngine
from core.product_proposal_store import ProductProposalStore
from core.product_builder import ProductBuilder
from core.product_plan_store import ProductPlanStore
from core.execution_engine import ExecutionEngine
from core.execution_focus_engine import ExecutionFocusEngine
from core.services.gumroad_sync_service import GumroadSyncService
from core.product_launch_store import ProductLaunchStore
from core.revenue_attribution.store import RevenueAttributionStore
from core.domain.integrity import DomainIntegrityError, DomainIntegrityPolicy
from core.errors import InvariantViolationError
from core.domain.lifecycle import EXECUTION_STATUSES
from core.reddit_public.config import get_config
from core.reddit_public.pain_scoring import compute_pain_score
from core.openclaw_agent import (
    OpenClawRedditScanner,
    normalize_openclaw_to_scan_summary,
)


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
        alignment_engine: AlignmentEngine | None = None,
        product_builder: ProductBuilder | None = None,
        product_plan_store: ProductPlanStore | None = None,
        execution_engine: ExecutionEngine | None = None,
        product_launch_store: ProductLaunchStore | None = None,
        revenue_attribution_store: RevenueAttributionStore | None = None,
        bus: EventBus | None = None,
    ):
        self.decision_engine = decision_engine or DecisionEngine()
        self.gumroad_client = gumroad_client
        self.action_planner = action_planner or ActionPlanner()
        self.confirmation_queue = confirmation_queue or ConfirmationQueue()

        inferred_dir = None
        for store in (product_proposal_store, product_plan_store, product_launch_store, opportunity_store):
            store_path = getattr(store, "_path", None)
            if isinstance(store_path, Path):
                inferred_dir = store_path.parent
                break

        if inferred_dir is None and (
            opportunity_store is None
            or product_proposal_store is None
            or product_plan_store is None
            or product_launch_store is None
        ):
            inferred_dir = Path(tempfile.mkdtemp(prefix="treta_control_"))

        self.opportunity_store = opportunity_store or OpportunityStore(
            path=(inferred_dir / "opportunities.json") if inferred_dir is not None else None
        )
        self.product_engine = product_engine or ProductEngine()
        self.product_proposal_store = product_proposal_store or ProductProposalStore(
            path=(inferred_dir / "product_proposals.json") if inferred_dir is not None else None
        )
        self.alignment_engine = alignment_engine or AlignmentEngine()
        self.product_builder = product_builder or ProductBuilder()
        self.product_plan_store = product_plan_store or ProductPlanStore(
            path=(inferred_dir / "product_plans.json") if inferred_dir is not None else None
        )
        self.execution_engine = execution_engine or ExecutionEngine()
        self.product_launch_store = product_launch_store or ProductLaunchStore(
            proposal_store=self.product_proposal_store,
            path=(inferred_dir / "product_launches.json") if inferred_dir is not None else None,
        )
        self.revenue_attribution_store = revenue_attribution_store or RevenueAttributionStore(
            path=(inferred_dir / "revenue_attribution.json") if inferred_dir is not None else None,
        )
        self.gumroad_sales_sync_service = (
            GumroadSyncService(self.product_launch_store, self.gumroad_client, self.revenue_attribution_store)
            if self.gumroad_client is not None
            else None
        )
        self._last_reddit_scan: Dict[str, object] | None = None
        self.only_top_proposal = True
        self.domain_integrity_policy = DomainIntegrityPolicy()
        self.bus = bus or EventBus()

    def has_active_proposal(self) -> bool:
        active_statuses = {"draft", *self.domain_integrity_policy.ACTIVE_STATUSES}
        return any(
            str(item.get("status", "")).strip() in active_statuses
            for item in self.product_proposal_store.list()
        )


    def _refresh_execution_focus(self) -> None:
        target_id = ExecutionFocusEngine.select_active(
            self.product_proposal_store._items,
            self.product_launch_store._items,
        )
        ExecutionFocusEngine.enforce_single_active(
            target_id,
            {"proposals": self.product_proposal_store._items, "launches": self.product_launch_store._items},
        )
        self.product_proposal_store._save()
        self.product_launch_store._save()


    def _validate_global(self) -> None:
        proposals = self.product_proposal_store.list()
        launches = self.product_launch_store.list()
        plans = self.product_plan_store.list()
        try:
            self.domain_integrity_policy.validate_global_invariants(
                proposals=proposals,
                launches=launches,
                plans=plans,
            )
        except DomainIntegrityError as exc:
            raise InvariantViolationError(str(exc)) from exc

    def _reddit_posts_path(self) -> Path:
        proposal_store_path = getattr(self.product_proposal_store, "_path", None)
        if isinstance(proposal_store_path, Path):
            data_dir = proposal_store_path.parent
        else:
            data_dir = Path(__file__).resolve().parent.parent / ".treta_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "reddit_posts.json"

    def _load_reddit_posts(self) -> list[dict]:
        path = self._reddit_posts_path()
        if not path.exists():
            return []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(loaded, list):
            return []
        return [item for item in loaded if isinstance(item, dict)]

    def _save_reddit_posts(self, items: list[dict]) -> None:
        self._reddit_posts_path().write_text(json.dumps(items, indent=2), encoding="utf-8")

    def run_reddit_public_scan(self) -> Dict[str, object]:
        from core.reddit_public.service import RedditPublicService

        config = get_config()
        pain_threshold = int(config.get("pain_threshold", 60))
        subreddits = [
            str(item).strip()
            for item in config.get("subreddits", [])
            if str(item).strip()
        ]

        posts = RedditPublicService().scan_subreddits(subreddits)
        print(
            f"[REDDIT_PUBLIC] analyzed {len(posts)} posts after score/comment filters; "
            f"pain_threshold={pain_threshold}"
        )

        qualified_posts: List[Dict[str, object]] = []
        ranked_candidates: List[Dict[str, object]] = []
        by_subreddit: Dict[str, int] = {}
        stored_posts = self._load_reddit_posts()
        known_post_ids = {
            str(item.get("post_id", "")).strip()
            for item in stored_posts
            if str(item.get("post_id", "")).strip()
        }

        for post in posts:
            post_id = str(post.get("id", "")).strip()
            if post_id and post_id in known_post_ids:
                continue

            title = str(post.get("title", ""))
            body = str(post.get("selftext", ""))
            pain_data = compute_pain_score(post)
            pain_score = int(pain_data["pain_score"])
            print(
                f"[REDDIT_PUBLIC] post={post.get('id', '')} pain_score={pain_score} "
                f"intent={pain_data['intent_type']} urgency={pain_data['urgency_level']}"
            )
            if pain_score < pain_threshold:
                continue

            qualified_payload = {
                "title": title,
                "subreddit": str(post.get("subreddit", "")),
                "pain_score": pain_score,
                "intent_type": str(pain_data["intent_type"]),
                "urgency_level": str(pain_data["urgency_level"]),
            }
            qualified_posts.append(qualified_payload)
            ranked_candidates.append(
                {
                    "post": post,
                    "pain_data": pain_data,
                    "pain_score": pain_score,
                    "score": pain_score,
                }
            )
            subreddit_name = str(post.get("subreddit", "")).strip() or "unknown"
            by_subreddit[subreddit_name] = by_subreddit.get(subreddit_name, 0) + 1
            if post_id:
                known_post_ids.add(post_id)
            stored_posts.append(
                {
                    "id": f"reddit_post_{int(datetime.utcnow().timestamp() * 1000)}_{post_id or len(stored_posts)}",
                    "post_id": post_id,
                    "proposal_id": "",
                    "product_name": "",
                    "subreddit": subreddit_name,
                    "post_url": str(post.get("url", "")).strip(),
                    "upvotes": int(post.get("score", 0) or 0),
                    "comments": int(post.get("num_comments", 0) or 0),
                    "status": "open",
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )

        self._save_reddit_posts(stored_posts)

        if ranked_candidates and not self.has_active_proposal():
            candidates = sorted(
                ranked_candidates,
                key=lambda item: (int(item["score"]), int(item["post"].get("score", 0))),
                reverse=True,
            )
            selected = candidates[0] if self.only_top_proposal else None
            if selected is not None:
                top_post = selected["post"]
                top_pain_data = selected["pain_data"]
                top_pain_score = int(selected["pain_score"])
                snippet = str(top_post.get("selftext", ""))[:300]
                self.bus.push(
                    Event(
                        type="OpportunityDetected",
                        payload={
                            "id": f"reddit-public-{top_post.get('id', '')}",
                            "source": "reddit_public",
                            "title": str(top_post.get("title", "")),
                            "subreddit": top_post.get("subreddit", ""),
                            "score": top_post.get("score", 0),
                            "num_comments": top_post.get("num_comments", 0),
                            "pain_score": top_pain_score,
                            "intent_type": top_pain_data["intent_type"],
                            "urgency_level": top_pain_data["urgency_level"],
                            "snippet": snippet,
                            "summary": snippet,
                            "opportunity": {
                                "confidence": min(10, max(1, int(top_post.get("score", 0) / 10) + 1)),
                            },
                        },
                        source="reddit_public_scan",
                    )
                )

        result = {
            "analyzed": len(posts),
            "qualified": len(qualified_posts),
            "by_subreddit": by_subreddit,
            "posts": qualified_posts,
        }
        self._last_reddit_scan = result
        return result

    def get_last_reddit_scan(self) -> Dict[str, object] | None:
        return self._last_reddit_scan

    def run_reddit_scan(self) -> Dict[str, object]:
        config = get_config()
        source = str(config.get("source", "reddit_public")).strip().lower()

        if source != "openclaw":
            return self.run_reddit_public_scan()

        try:
            result = self.run_openclaw_reddit_scan()
            print(
                f"[OPENCLAW] scan ok: analyzed={int(result.get('analyzed', 0))} "
                f"qualified={int(result.get('qualified', 0))}"
            )
            return result
        except Exception as exc:
            print(f"[OPENCLAW] failed -> falling back to reddit_public: {exc}")
            fallback = self.run_reddit_public_scan()
            diagnostics = {
                "source": "openclaw",
                "fallback_to": "reddit_public",
                "error": str(exc),
            }
            fallback_with_diagnostics = dict(fallback)
            fallback_with_diagnostics["diagnostics"] = diagnostics
            self._last_reddit_scan = fallback_with_diagnostics
            return fallback_with_diagnostics

    def _scan_reddit_public_opportunities(self) -> None:
        self.run_reddit_scan()

    def run_openclaw_reddit_scan(self) -> Dict[str, object]:
        config = get_config()
        subreddits = [
            str(item).strip()
            for item in config.get("subreddits", [])
            if str(item).strip()
        ]
        scan_data = OpenClawRedditScanner().scan(subreddits=subreddits, limit=10)
        result = normalize_openclaw_to_scan_summary(scan_data)
        self._last_reddit_scan = result
        return result

    def _generate_reddit_daily_plan(self) -> None:
        from core.reddit_intelligence.daily_plan_store import RedditDailyPlanStore
        from core.reddit_intelligence.service import RedditIntelligenceService

        signals = RedditIntelligenceService().get_daily_top_actions(limit=5)
        signal_ids = [str(item.get("id", "")).strip() for item in signals if str(item.get("id", "")).strip()]

        summary_lines = ["Today's Reddit focus:"]
        for index, signal in enumerate(signals, start=1):
            subreddit = str(signal.get("subreddit", "unknown")).strip() or "unknown"
            pain = str(signal.get("detected_pain_type", "trend")).strip() or "trend"
            summary_lines.append(f"{index}. r/{subreddit} - {pain} signal")

        if len(summary_lines) == 1:
            summary_lines.append("No high-priority Reddit signals identified today.")

        plan = {
            "generated_at": datetime.utcnow().isoformat(),
            "signals": signal_ids,
            "summary": "\n".join(summary_lines),
        }
        RedditDailyPlanStore.save(plan)
        self.bus.push(Event(type="RedditDailyPlanGenerated", payload=plan, source="control"))

    def link_launch_gumroad(self, launch_id: str, gumroad_product_id: str) -> Dict[str, object]:
        updated = self.product_launch_store.link_gumroad_product(launch_id, gumroad_product_id)
        self._validate_global()
        return updated

    def sync_gumroad_sales(self) -> Dict[str, object]:
        if self.gumroad_sales_sync_service is None:
            raise ValueError("Missing Gumroad access token. Set GUMROAD_ACCESS_TOKEN.")
        return self.gumroad_sales_sync_service.sync_sales()

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
            self._scan_reddit_public_opportunities()
            self._generate_reddit_daily_plan()
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
                summary=str(event.payload.get("summary", event.payload.get("snippet", ""))),
                opportunity=dict(event.payload.get("opportunity", {})),
            )

            if created.get("source") == "reddit_public" and self.has_active_proposal():
                return []

            alignment = self.alignment_engine.evaluate(
                created,
                {
                    "recent_proposals": self.product_proposal_store.list()[:5],
                },
            )
            if not alignment["aligned"]:
                self.opportunity_store.set_status(created["id"], "strategically_filtered")
                return []

            proposal = self.product_engine.generate(created)
            proposal["alignment_score"] = alignment["alignment_score"]
            proposal["alignment_reason"] = alignment["reason"]
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
            next_status = proposal_transitions[event.type]
            proposal = self.product_proposal_store.get(proposal_id)
            if proposal is None:
                return []
            proposals = self.product_proposal_store.list()
            self.domain_integrity_policy.validate_transition(proposal, next_status, proposals)
            updated = self.product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status=next_status,
            )
            self._validate_global()
            if updated["status"] in EXECUTION_STATUSES:
                self._refresh_execution_focus()
                updated = self.product_proposal_store.get(updated["id"]) or updated
            actions = [
                Action(
                    type="ProductProposalStatusChanged",
                    payload={"proposal_id": updated["id"], "status": updated["status"], "proposal": updated},
                )
            ]
            if event.type == "MarkProposalLaunched":
                launch = self.product_launch_store.add_from_proposal(updated["id"])
                launch = self.product_launch_store.mark_launched(launch["id"])
                self._validate_global()
                self._refresh_execution_focus()
                launch = self.product_launch_store.get(launch["id"]) or launch
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
            self._validate_global()
            return [Action(type="ProductLaunchUpdated", payload={"launch": updated})]

        if event.type == "BuildProductPlanRequested":
            proposal_id = str(event.payload.get("proposal_id", ""))
            proposal = self.product_proposal_store.get(proposal_id)
            if proposal is None:
                return []

            if str(proposal.get("status", "")).strip() == "draft" and str(proposal.get("source_opportunity_id", "")).strip():
                proposals = self.product_proposal_store.list()
                self.domain_integrity_policy.validate_transition(proposal, "approved", proposals)
                proposal = self.product_proposal_store.transition_status(
                    proposal_id=proposal_id,
                    new_status="approved",
                )
                self._validate_global()

            self.domain_integrity_policy.validate_plan_build_precondition(proposal)

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
            self._validate_global()
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
            tracking_id = f"treta-{proposal_id[:6]}-{int(datetime.utcnow().timestamp())}"
            reddit_post = execution_package.get("reddit_post")
            if isinstance(reddit_post, dict):
                reddit_post["body"] = f"{str(reddit_post.get('body', '')).rstrip()}\n\nTracking: {tracking_id}"
            execution_package["gumroad_description"] = (
                f"{str(execution_package.get('gumroad_description', '')).rstrip()}\n\nTracking: {tracking_id}"
            )
            execution_package["short_pitch"] = (
                f"{str(execution_package.get('short_pitch', '')).rstrip()} (Tracking: {tracking_id})"
            )

            source_opportunity_id = str(proposal.get("source_opportunity_id", "")).strip()
            subreddit = None
            if source_opportunity_id:
                opportunity = self.opportunity_store.get(source_opportunity_id)
                if opportunity is not None:
                    subreddit = opportunity.get("subreddit") or opportunity.get("opportunity", {}).get("subreddit")

            self.revenue_attribution_store.upsert_tracking(
                tracking_id=tracking_id,
                proposal_id=proposal_id,
                subreddit=str(subreddit).strip() if subreddit else None,
                price=proposal.get("price_suggestion"),
                created_at=datetime.utcnow().isoformat() + "Z",
            )
            print(f"[EXECUTION] proposal_id={proposal_id}")
            actions = [
                Action(
                    type="ProductPlanExecuted",
                    payload={
                        "proposal_id": proposal_id,
                        "execution_package": execution_package,
                        "tracking_id": tracking_id,
                    },
                )
            ]

            proposals = self.product_proposal_store.list()
            self.domain_integrity_policy.validate_transition(proposal, "ready_for_review", proposals)
            updated = self.product_proposal_store.transition_status(
                proposal_id=proposal_id,
                new_status="ready_for_review",
            )
            self._validate_global()
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
