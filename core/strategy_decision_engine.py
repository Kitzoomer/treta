from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from core.domain.strategy_plan import StrategyPlan
from core.performance_engine import PerformanceEngine
from core.product_launch_store import ProductLaunchStore


class StrategyDecisionEngine:
    """Deterministic strategic decisions derived from launch performance."""

    def __init__(
        self,
        product_launch_store: ProductLaunchStore,
        decision_id_factory: Callable[[], str] | None = None,
    ):
        self._product_launch_store = product_launch_store
        self._performance_engine = PerformanceEngine(product_launch_store=product_launch_store)
        self._decision_id_factory = decision_id_factory

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

    def decide(self, request_id: str | None = None, trace_id: str | None = None, event_id: str | None = None) -> StrategyPlan:
        launches = self._product_launch_store.list()

        actions: List[Dict[str, Any]] = []
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
                actions.append(
                    {
                        "type": "draft_asset",
                        "target_id": launch_id,
                        "reasoning": "Create a safe draft landing/email asset to improve launch messaging.",
                    }
                )
                actions.append(
                    {
                        "type": "queue_openclaw_task",
                        "target_id": launch_id,
                        "reasoning": "Queue a non-destructive external analysis task for stalled launch diagnostics.",
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

        primary_focus = "stabilize"
        if any(action["type"] == "scale" for action in actions):
            primary_focus = "growth"
        elif any(action["type"] == "price_test" for action in actions):
            primary_focus = "optimization"
        elif any(action["type"] == "new_product" for action in actions):
            primary_focus = "pipeline"

        priority_level = "low"
        if any(action["type"] in {"scale", "review"} for action in actions):
            priority_level = "high"
        elif actions:
            priority_level = "medium"

        confidence = 10 if actions else 8
        context_snapshot: Dict[str, Any] = {
            "request_id": str(request_id or "").strip() or None,
            "trace_id": str(trace_id or "").strip() or None,
            "event_id": str(event_id or "").strip() or None,
            "launch_count": len(launches),
            "total_sales": self._performance_engine.total_sales(),
            "total_revenue": self._performance_engine.total_revenue(),
            "priority_level": priority_level,
            "primary_focus": primary_focus,
            "risk_flags": risk_flags,
            "confidence": confidence,
        }

        return StrategyPlan.create(
            decision_id=self._decision_id_factory() if self._decision_id_factory is not None else None,
            context_snapshot=context_snapshot,
            recommended_actions=actions,
            autonomy_intent={
                "should_execute": bool(actions),
                "reason": "actions_available" if actions else "no_actions",
                "metadata": {
                    "priority_level": priority_level,
                    "primary_focus": primary_focus,
                    "risk_flags": risk_flags,
                },
            },
        )
