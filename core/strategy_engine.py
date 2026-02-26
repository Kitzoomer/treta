from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from core.performance_engine import PerformanceEngine
from core.product_launch_store import ProductLaunchStore
from core.coherence_check_engine import CoherenceCheckEngine
from core.output_validator import OutputValidator
from core.strategic_executor_engine import StrategicExecutorEngine
from core.strategic_planner_engine import StrategicPlannerEngine


class StrategyEngine:
    """Deterministic strategy recommendations derived from launch performance."""

    def __init__(
        self,
        product_launch_store: ProductLaunchStore,
        strategic_planner_engine: StrategicPlannerEngine | None = None,
        strategic_executor_engine: StrategicExecutorEngine | None = None,
        coherence_check_engine: CoherenceCheckEngine | None = None,
    ):
        self._product_launch_store = product_launch_store
        self._performance_engine = PerformanceEngine(product_launch_store=product_launch_store)
        self._strategic_planner_engine = strategic_planner_engine or StrategicPlannerEngine()
        self._strategic_executor_engine = strategic_executor_engine or StrategicExecutorEngine()
        self._coherence_check_engine = coherence_check_engine or CoherenceCheckEngine()
        self._output_validator = OutputValidator()
        self._logger = logging.getLogger("treta.strategy.engine")

    def _launches(self) -> List[Dict[str, Any]]:
        return self._product_launch_store.list()

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

    def generate_recommendations(self) -> Dict[str, Any]:
        launches = self._launches()
        total_revenue = self._performance_engine.total_revenue()
        total_sales = self._performance_engine.total_sales()
        revenue_by_product = self._performance_engine.revenue_by_product()
        revenue_by_category = self._performance_engine.revenue_by_product_type()

        product_actions = []
        for item in sorted(launches, key=lambda launch: str(launch.get("id", ""))):
            sales = int(item.get("metrics", {}).get("sales", 0) or 0)
            revenue = round(float(item.get("metrics", {}).get("revenue", 0.0) or 0.0), 2)
            days_since_launch = self._days_since_launch(item.get("created_at"))

            action = None
            reason = None
            confidence = None

            if sales >= 5 and revenue >= 100:
                action = "SCALE_PRODUCT"
                reason = f"{sales} sales and ${revenue:.2f} revenue meet scale thresholds."
                confidence = 92
            elif sales > 0 and revenue < 50:
                action = "TEST_PRICE"
                reason = f"{sales} sales but only ${revenue:.2f} revenue indicates price optimization opportunity."
                confidence = 84
            elif sales == 0 and days_since_launch > 7:
                action = "FIX_OR_ARCHIVE"
                reason = f"No sales after {days_since_launch} days since launch."
                confidence = 88

            if action is not None:
                product_actions.append(
                    {
                        "product_id": str(item.get("id") or ""),
                        "action": action,
                        "reason": reason,
                        "confidence": confidence,
                    }
                )

        category_actions = []
        if total_revenue > 0:
            for category, revenue in sorted(revenue_by_category.items()):
                share = revenue / total_revenue
                if share >= 0.60:
                    category_actions.append(
                        {
                            "category": category,
                            "action": "CATEGORY_EXPANSION",
                            "reason": f"Category contributes {share:.0%} of total revenue (${revenue:.2f}/${total_revenue:.2f}).",
                            "confidence": 90,
                        }
                    )

        global_summary = {
            "total_revenue": total_revenue,
            "total_sales": total_sales,
            "revenue_by_product": revenue_by_product,
            "revenue_by_category": revenue_by_category,
            "days_since_launch": {
                str(item.get("id") or ""): self._days_since_launch(item.get("created_at"))
                for item in sorted(launches, key=lambda launch: str(launch.get("id", "")))
            },
        }

        return {
            "global_summary": global_summary,
            "product_actions": product_actions,
            "category_actions": category_actions,
        }

    def run_strategic_plan(self, objective: str, state_snapshot: str) -> Dict[str, Any]:
        self._logger.info(
            "Starting strategic Plan→Execute",
            extra={"phase": "plan_execute", "objective": objective, "task_type": "planning_cycle"},
        )
        plan = self._strategic_planner_engine.create_plan(objective=objective, state_snapshot=state_snapshot)

        self._output_validator.validate_required_fields(plan, ["objective", "steps"])
        self._output_validator.validate_schema(plan, {"objective": "string", "steps": []})
        self._output_validator.validate_non_empty_strings(plan)

        coherence = self._coherence_check_engine.evaluate(plan=plan, snapshot=state_snapshot)
        coherence_payload = {
            "is_coherent": coherence.is_coherent,
            "contradictions": coherence.contradictions,
            "drastic_changes": coherence.drastic_changes,
            "requires_human_review": coherence.requires_human_review,
        }

        if coherence.requires_human_review:
            self._logger.warning(
                "Strategic plan blocked due to coherence drift",
                extra={
                    "phase": "plan_execute",
                    "task_type": "coherence_check",
                    "objective": objective,
                    "requires_human_review": True,
                    "contradictions": len(coherence.contradictions),
                    "drastic_changes": len(coherence.drastic_changes),
                },
            )
            return {
                "plan": plan,
                "execution": {
                    "objective": str(plan.get("objective") or ""),
                    "status": "blocked_for_human_review",
                    "total_steps": 0,
                    "completed_steps": 0,
                    "results": [],
                },
                "coherence": coherence_payload,
            }

        result = self._strategic_executor_engine.execute_plan(plan=plan)
        return {
            "plan": plan,
            "execution": result,
            "coherence": coherence_payload,
        }
