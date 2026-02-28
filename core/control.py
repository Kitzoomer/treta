from dataclasses import dataclass
import logging
import tempfile
from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List

from core.events import Event, make_event
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
from core.subreddit_performance_store import SubredditPerformanceStore
from core.domain.integrity import DomainIntegrityError, DomainIntegrityPolicy
from core.errors import InvariantViolationError
from core.domain.lifecycle import EXECUTION_STATUSES
from core.reddit_public.config import get_config
from core.reddit_public.pain_scoring import compute_pain_score
from core.storage import Storage
from core.strategy_decision_engine import StrategyDecisionEngine
from core.services.strategy_decision_orchestrator import StrategyDecisionOrchestrator
from core.handlers.strategy_handler import StrategyHandler
from core.handlers.opportunity_handler import OpportunityHandler
from core.handlers.scan_handler import ScanHandler
from core.handlers.autonomy_handler import AutonomyHandler
from core.event_catalog import EventType

from core.openclaw_agent import (
    OpenClawRedditScanner,
    normalize_openclaw_to_scan_summary,
)


@dataclass(frozen=True)
class Action:
    type: str
    payload: Dict[str, object]


logger = logging.getLogger("treta.control")


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
        subreddit_performance_store: SubredditPerformanceStore | None = None,
        strategy_decision_engine: StrategyDecisionEngine | None = None,
        strategy_decision_orchestrator: StrategyDecisionOrchestrator | None = None,
        strategy_action_execution_layer = None,
        bus: EventBus | None = None,
    ):
        self.decision_engine = decision_engine or DecisionEngine(storage=Storage())
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
        self.subreddit_performance_store = subreddit_performance_store or SubredditPerformanceStore(
            path=(inferred_dir / "subreddit_performance.json") if inferred_dir is not None else None,
        )
        self.strategy_decision_engine = strategy_decision_engine
        self.strategy_decision_orchestrator = strategy_decision_orchestrator
        self.strategy_action_execution_layer = strategy_action_execution_layer
        self.gumroad_sales_sync_service = (
            GumroadSyncService(
                self.product_launch_store,
                self.gumroad_client,
                self.revenue_attribution_store,
                self.subreddit_performance_store,
            )
            if self.gumroad_client is not None
            else None
        )
        self._last_reddit_scan: Dict[str, object] | None = None
        self.only_top_proposal = True
        self.domain_integrity_policy = DomainIntegrityPolicy()
        self.bus = bus or EventBus()

    def _revenue_summary(self) -> dict:
        if self.revenue_attribution_store is None:
            return {}
        summary = self.revenue_attribution_store.summary()
        return summary if isinstance(summary, dict) else {}


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

    def _compute_ranking_bonuses(self, subreddit: str) -> dict[str, float]:
        stats = self.subreddit_performance_store.get_subreddit_stats(subreddit)
        posts_attempted = int(stats.get("posts_attempted", 0) or 0)
        performance_sales = int(stats.get("sales", 0) or 0)

        by_subreddit = self._revenue_summary().get("by_subreddit", {})
        revenue_stats = by_subreddit.get(subreddit, {}) if isinstance(by_subreddit, dict) else {}
        sales = int(revenue_stats.get("sales", performance_sales) or 0)
        revenue = float(revenue_stats.get("revenue", 0.0) or 0.0)

        revenue_bonus = round(min(50.0, revenue / 2.0), 2)
        conversion_rate = sales / max(posts_attempted, 1)
        conversion_bonus = round(min(30.0, conversion_rate * 100.0), 2)

        return {
            "revenue_bonus": revenue_bonus,
            "execution_bonus": 0.0,
            "conversion_bonus": conversion_bonus,
            # Backward-compatible aliases for existing API response keys.
            "roi_priority_bonus": revenue_bonus,
            "zero_roi_penalty": 0.0,
            "throttle_penalty": 0.0,
        }

    def _compute_subreddit_roi(self, subreddit_stats: dict[str, object]) -> float:
        posts_attempted = int(subreddit_stats.get("posts_attempted", 0) or 0)
        if posts_attempted == 0:
            return 0.0
        subreddit = str(subreddit_stats.get("name", "")).strip()
        by_subreddit = self._revenue_summary().get("by_subreddit", {})
        revenue_stats = by_subreddit.get(subreddit, {}) if isinstance(by_subreddit, dict) else {}
        revenue = float(revenue_stats.get("revenue", 0.0) or 0.0)
        return revenue / posts_attempted

    def _get_top_subreddits_by_roi(self, limit: int = 2) -> list[str]:
        summary = self.subreddit_performance_store.get_summary()
        rows = list(summary.get("subreddits", [])) if isinstance(summary, dict) else []
        ranked = sorted(
            [item for item in rows if isinstance(item, dict)],
            key=lambda item: (
                self._compute_subreddit_roi(item),
                float(item.get("revenue", 0.0) or 0.0),
                int(self._revenue_summary().get("by_subreddit", {}).get(str(item.get("name", "")).strip(), {}).get("sales", 0) or 0),
            ),
            reverse=True,
        )
        return [str(item.get("name", "")).strip() for item in ranked[: max(0, int(limit))] if str(item.get("name", "")).strip()]

    def get_dominant_subreddits(self, limit: int = 2) -> dict[str, object]:
        summary = self.subreddit_performance_store.get_summary()
        rows = list(summary.get("subreddits", [])) if isinstance(summary, dict) else []
        return {
            "dominant_subreddits": self._get_top_subreddits_by_roi(limit=limit),
            "total_tracked": len([item for item in rows if isinstance(item, dict)]),
        }

    def run_reddit_public_scan(self) -> Dict[str, object]:
        from core.reddit_public.service import RedditPublicService

        config = get_config()
        pain_threshold = int(config.get("pain_threshold", 60))
        subreddits = [
            str(item).strip()
            for item in config.get("subreddits", [])
            if str(item).strip()
        ]

        summary = self.subreddit_performance_store.get_summary()
        stats_rows = list(summary.get("subreddits", [])) if isinstance(summary, dict) else []
        warmed_subreddits = [
            item
            for item in stats_rows
            if isinstance(item, dict) and int(item.get("posts_attempted", 0) or 0) >= 3
        ]
        dominant_subreddits: list[str] = []
        if len(warmed_subreddits) >= 2:
            dominant_subreddits = self._get_top_subreddits_by_roi(limit=2)
            allowed = set(dominant_subreddits)
            subreddits = [name for name in subreddits if name in allowed]

        posts = RedditPublicService().scan_subreddits(subreddits)
        logger.info(
            f"[REDDIT_PUBLIC] analyzed {len(posts)} posts after score/comment filters; "
            f"pain_threshold={pain_threshold}"
        )

        qualified_posts: List[Dict[str, object]] = []
        ranked_candidates: List[Dict[str, object]] = []
        by_subreddit: Dict[str, int] = {}
        throttled_subreddits: set[str] = set()
        skipped_due_to_channel_lock: list[str] = []
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
            subreddit_name = str(post.get("subreddit", "")).strip() or "unknown"
            bonuses = self._compute_ranking_bonuses(subreddit_name)
            revenue_bonus = round(float(bonuses["revenue_bonus"]), 2)
            execution_bonus = round(float(bonuses["execution_bonus"]), 2)
            conversion_bonus = round(float(bonuses["conversion_bonus"]), 2)
            roi_priority_bonus = round(float(bonuses["roi_priority_bonus"]), 2)
            zero_roi_penalty = round(float(bonuses["zero_roi_penalty"]), 2)
            throttle_penalty = round(float(bonuses["throttle_penalty"]), 2)
            final_score = round(pain_score + revenue_bonus + execution_bonus + conversion_bonus, 2)
            logger.info(
                f"[REDDIT_PUBLIC] post={post.get('id', '')} pain_score={pain_score} "
                f"bonuses=(revenue={revenue_bonus},exec={execution_bonus},conv={conversion_bonus}) final_score={final_score} "
                f"intent={pain_data['intent_type']} urgency={pain_data['urgency_level']}"
            )
            if pain_score < pain_threshold:
                continue

            qualified_payload = {
                "title": title,
                "subreddit": subreddit_name,
                "pain_score": pain_score,
                "revenue_bonus": revenue_bonus,
                "execution_bonus": execution_bonus,
                "conversion_bonus": conversion_bonus,
                "roi_priority_bonus": roi_priority_bonus,
                "zero_roi_penalty": zero_roi_penalty,
                "throttle_penalty": throttle_penalty,
                "score": final_score,
                "intent_type": str(pain_data["intent_type"]),
                "urgency_level": str(pain_data["urgency_level"]),
            }
            qualified_posts.append(qualified_payload)
            ranked_candidates.append(
                {
                    "post": post,
                    "pain_data": pain_data,
                    "pain_score": pain_score,
                    "revenue_bonus": revenue_bonus,
                    "execution_bonus": execution_bonus,
                    "conversion_bonus": conversion_bonus,
                    "roi_priority_bonus": roi_priority_bonus,
                    "zero_roi_penalty": zero_roi_penalty,
                    "throttle_penalty": throttle_penalty,
                    "score": final_score,
                }
            )
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
                top_subreddit = str(top_post.get("subreddit", "")).strip() or "unknown"
                if dominant_subreddits and top_subreddit not in set(dominant_subreddits):
                    skipped_due_to_channel_lock.append(top_subreddit)
                else:
                    top_pain_data = selected["pain_data"]
                    top_pain_score = int(selected["pain_score"])
                    top_revenue_bonus = int(selected.get("revenue_bonus", 0) or 0)
                    top_execution_bonus = int(selected.get("execution_bonus", 0) or 0)
                    top_conversion_bonus = int(selected.get("conversion_bonus", 0) or 0)
                    top_roi_priority_bonus = int(selected.get("roi_priority_bonus", 0) or 0)
                    top_zero_roi_penalty = int(selected.get("zero_roi_penalty", 0) or 0)
                    top_throttle_penalty = int(selected.get("throttle_penalty", 0) or 0)
                    top_final_score = int(selected.get("score", top_pain_score) or top_pain_score)
                    snippet = str(top_post.get("selftext", ""))[:300]
                    self.subreddit_performance_store.record_post_attempt(top_subreddit)
                    self.bus.push(
                        Event(
                            type="OpportunityDetected",
                            payload={
                                "id": f"reddit-public-{top_post.get('id', '')}",
                                "source": "reddit_public",
                                "title": str(top_post.get("title", "")),
                                "subreddit": top_post.get("subreddit", ""),
                                "reddit_score": top_post.get("score", 0),
                                "num_comments": top_post.get("num_comments", 0),
                                "pain_score": top_pain_score,
                                "revenue_bonus": top_revenue_bonus,
                                "execution_bonus": top_execution_bonus,
                                "conversion_bonus": top_conversion_bonus,
                                "roi_priority_bonus": top_roi_priority_bonus,
                                "zero_roi_penalty": top_zero_roi_penalty,
                                "throttle_penalty": top_throttle_penalty,
                                "score": top_final_score,
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
        diagnostics: dict[str, object] = {}
        if throttled_subreddits:
            diagnostics["throttled_subreddits"] = sorted(throttled_subreddits)
        if dominant_subreddits:
            diagnostics["dominant_subreddits"] = dominant_subreddits
        if skipped_due_to_channel_lock:
            diagnostics["skipped_due_to_channel_lock"] = skipped_due_to_channel_lock
        if diagnostics:
            result["diagnostics"] = diagnostics
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
            logger.info(
                f"[OPENCLAW] scan ok: analyzed={int(result.get('analyzed', 0))} "
                f"qualified={int(result.get('qualified', 0))}"
            )
            return result
        except Exception as exc:
            logger.info(f"[OPENCLAW] failed -> falling back to reddit_public: {exc}")
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
        self.bus.push(make_event(EventType.REDDIT_DAILY_PLAN_GENERATED, plan, source="control"))

    def link_launch_gumroad(self, launch_id: str, gumroad_product_id: str) -> Dict[str, object]:
        updated = self.product_launch_store.link_gumroad_product(launch_id, gumroad_product_id)
        self._validate_global()
        return updated

    def sync_gumroad_sales(self) -> Dict[str, object]:
        if self.gumroad_sales_sync_service is None:
            raise ValueError("Missing Gumroad access token. Set GUMROAD_ACCESS_TOKEN.")
        return self.gumroad_sales_sync_service.sync_sales()

    def _correlation_id_from_event(self, event: Event) -> str:
        request_id = str(event.request_id or event.payload.get("request_id", "") if isinstance(event.payload, dict) else "").strip()
        trace_id = str(event.trace_id or event.payload.get("trace_id", "") if isinstance(event.payload, dict) else "").strip()
        event_id = str(event.event_id).strip()
        parts = []
        if request_id:
            parts.append(f"request:{request_id}")
        if trace_id:
            parts.append(f"trace:{trace_id}")
        if event_id:
            parts.append(f"event:{event_id}")
        return "|".join(parts)

    def evaluate_opportunity(
        self,
        opportunity: Dict[str, object],
        request_id: str | None = None,
        trace_id: str | None = None,
        event_id: str | None = None,
    ) -> Dict[str, object]:
        return self.decision_engine.evaluate(
            opportunity,
            request_id=request_id,
            trace_id=trace_id,
            event_id=event_id,
        )

    def consume(self, event: Event) -> List[Action]:
        logger.info("Control consume", extra={"event_type": event.type, "request_id": event.request_id, "trace_id": event.trace_id, "event_id": event.event_id, "decision_id": str(event.payload.get("decision_id", "")) if isinstance(event.payload, dict) else ""})

        context = {
            "Action": Action,
            "control": self,
            "stores": {
                "confirmation_queue": self.confirmation_queue,
                "opportunity_store": self.opportunity_store,
                "product_proposal_store": self.product_proposal_store,
                "product_plan_store": self.product_plan_store,
                "product_launch_store": self.product_launch_store,
                "revenue_attribution_store": self.revenue_attribution_store,
                "subreddit_performance_store": self.subreddit_performance_store,
            },
            "engines": {
                "action_planner": self.action_planner,
                "alignment_engine": self.alignment_engine,
                "decision_engine": self.decision_engine,
                "execution_engine": self.execution_engine,
                "gumroad_client": self.gumroad_client,
                "product_builder": self.product_builder,
                "product_engine": self.product_engine,
                "strategy_decision_engine": self.strategy_decision_engine,
                "strategy_decision_orchestrator": self.strategy_decision_orchestrator,
            },
            "dispatcher": self.bus,
            "storage": getattr(self.decision_engine, "storage", None) or getattr(self.decision_engine, "_storage", None),
            "strategy_action_execution_layer": self.strategy_action_execution_layer,
        }

        handlers = {
            "DailyBriefRequested": ScanHandler,
            "OpportunityScanRequested": ScanHandler,
            "RunInfoproductScan": ScanHandler,
            "EmailTriageRequested": ScanHandler,
            "GumroadStatsRequested": ScanHandler,
            "ActionApproved": AutonomyHandler,
            "ActionPlanGenerated": AutonomyHandler,
            "ListPendingConfirmations": AutonomyHandler,
            "ConfirmAction": AutonomyHandler,
            "RejectAction": AutonomyHandler,
            "OpportunityDetected": OpportunityHandler,
            "ListProductProposals": OpportunityHandler,
            "GetProductProposalById": OpportunityHandler,
            "ApproveProposal": OpportunityHandler,
            "RejectProposal": OpportunityHandler,
            "StartBuildingProposal": OpportunityHandler,
            "MarkReadyToLaunch": OpportunityHandler,
            "MarkProposalLaunched": OpportunityHandler,
            "ArchiveProposal": OpportunityHandler,
            "ListProductLaunchesRequested": OpportunityHandler,
            "GetProductLaunchRequested": OpportunityHandler,
            "AddProductLaunchSale": OpportunityHandler,
            "TransitionProductLaunchStatus": OpportunityHandler,
            "BuildProductPlanRequested": OpportunityHandler,
            "ListProductPlansRequested": OpportunityHandler,
            "GetProductPlanRequested": OpportunityHandler,
            "ExecuteProductPlanRequested": OpportunityHandler,
            "ListOpportunities": OpportunityHandler,
            "EvaluateOpportunityById": OpportunityHandler,
            "OpportunityDismissed": OpportunityHandler,
            "EvaluateOpportunity": StrategyHandler,
            "RunStrategyDecision": StrategyHandler,
            "ExecuteStrategyAction": StrategyHandler,
        }

        handler = handlers.get(event.type)
        if handler is None:
            return []

        try:
            return handler.handle(event, context)
        except Exception:
            logger.exception("Control handler failure", extra={"event_type": event.type, "event_id": event.event_id})
            raise
