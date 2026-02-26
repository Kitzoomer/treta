from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from core.performance_engine import PerformanceEngine
from core.product_launch_store import ProductLaunchStore
from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.storage import Storage


class StrategyDecisionEngine:
    """Deterministic strategic decisions derived from launch performance."""

    def __init__(
        self,
        product_launch_store: ProductLaunchStore,
        storage: Storage,
        strategy_action_execution_layer: StrategyActionExecutionLayer | None = None,
        autonomy_policy_engine: AutonomyPolicyEngine | None = None,
    ):
        self._product_launch_store = product_launch_store
        self._performance_engine = PerformanceEngine(product_launch_store=product_launch_store)
        self._strategy_action_execution_layer = strategy_action_execution_layer
        self._autonomy_policy_engine = autonomy_policy_engine
        self._storage = storage
        self._logger = logging.getLogger("treta.strategy.decision")

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _days_since_launch(self, created_at: str | None) -> int:
        created_at_dt = self._parse_datetime(created_at)
        if created_at_dt is None:
            return 0
        if created_at_dt.tzinfo is None:
            created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
        delta = self._utcnow() - created_at_dt.astimezone(timezone.utc)
        return max(int(delta.total_seconds() // 86400), 0)

    def decide(self, request_id: str | None = None, trace_id: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        launches = self._product_launch_store.list()

        request_ref = str(request_id or "").strip() or None
        trace_ref = str(trace_id or "").strip() or None
        event_ref = str(event_id or "").strip() or None

        actions: List[Dict[str, str]] = []
        risk_flags: List[str] = []

        for launch in sorted(launches, key=lambda item: str(item.get("id", ""))):
            launch_id = str(launch.get("id") or "")
            metrics = launch.get("metrics", {})
            sales = int(metrics.get("sales", 0) or 0)
            revenue = float(metrics.get("revenue", 0.0) or 0.0)
            revenue_per_sale = (revenue / sales) if sales > 0 else 0.0
            days_since_launch = self._days_since_launch(launch.get("created_at"))

            if sales >= 5:
                actions.append(
                    {
                        "type": "scale",
                        "target_id": launch_id,
                        "sales": sales,
                        "reasoning": f"Launch has {sales} sales, which meets the scale threshold.",
                    }
                )

            if sales == 0 and days_since_launch > 7:
                actions.append(
                    {
                        "type": "review",
                        "target_id": launch_id,
                        "reasoning": f"Launch has 0 sales after {days_since_launch} days.",
                    }
                )
                if "stalled_launch" not in risk_flags:
                    risk_flags.append("stalled_launch")

            if revenue_per_sale > 40 and sales < 3:
                actions.append(
                    {
                        "type": "price_test",
                        "target_id": launch_id,
                        "reasoning": (
                            f"Revenue per sale is {revenue_per_sale:.2f} with only {sales} total sales."
                        ),
                    }
                )
                if "low_volume_high_ticket" not in risk_flags:
                    risk_flags.append("low_volume_high_ticket")

        has_active_launch = any(str(item.get("status", "")) == "active" for item in launches)
        if not has_active_launch:
            actions.append(
                {
                    "type": "new_product",
                    "target_id": "portfolio",
                    "reasoning": "No active launches were found.",
                }
            )
            if "no_active_launches" not in risk_flags:
                risk_flags.append("no_active_launches")


        if self._autonomy_policy_engine is not None:
            actions = self._autonomy_policy_engine.prioritize_strategy_actions(actions)

        primary_focus = "stabilize"
        if any(action["type"] == "scale" for action in actions):
            primary_focus = "growth"
        elif any(action["type"] == "review" for action in actions):
            primary_focus = "stabilize"
        elif any(action["type"] == "price_test" for action in actions):
            primary_focus = "optimization"
        elif any(action["type"] == "new_product" for action in actions):
            primary_focus = "pipeline"

        priority_level = "low"
        if any(action["type"] in {"scale", "review"} for action in actions):
            priority_level = "high"
        elif actions:
            priority_level = "medium"

        decision_log_id: str | None = None
        try:
            decision_log_id = str(
                self._storage.create_decision_log(
                    {
                        "decision_type": "strategy_action",
                        "entity_type": "portfolio",
                        "entity_id": "global",
                        "action_type": "recommend",
                        "decision": "RECOMMEND",
                        "risk_score": float(10 if actions else 8),
                        "policy_name": "StrategyDecisionEngine",
                        "policy_snapshot_json": {
                            "rules": ["sales_scale_threshold", "stalled_launch_rule", "portfolio_activity_rule"],
                            "priority_level": priority_level,
                        },
                        "inputs_json": {"launch_count": len(launches)},
                        "outputs_json": {"actions": actions, "risk_flags": risk_flags},
                        "reason": f"Primary focus resolved to {primary_focus}.",
                        "correlation_id": request_ref,
                        "request_id": request_ref,
                        "trace_id": trace_ref,
                        "event_id": event_ref,
                        "status": "recorded",
                    }
                )
            )
        except Exception as exc:
            self._logger.exception("Failed to persist strategy decision log", extra={"request_id": request_ref, "trace_id": trace_ref, "event_id": event_ref, "error": str(exc)})

        if self._strategy_action_execution_layer is not None:
            self._strategy_action_execution_layer.register_pending_actions(
                actions,
                decision_id=decision_log_id,
                event_id=event_ref,
                trace_id=trace_ref,
            )

        if self._autonomy_policy_engine is not None:
            self._autonomy_policy_engine.apply(request_id=request_ref)

        confidence = 10 if actions else 8

        result = {
            "priority_level": priority_level,
            "primary_focus": primary_focus,
            "actions": actions,
            "risk_flags": risk_flags,
            "confidence": confidence,
            "context": {
                "total_sales": self._performance_engine.total_sales(),
                "total_revenue": self._performance_engine.total_revenue(),
            },
        }
        return result
