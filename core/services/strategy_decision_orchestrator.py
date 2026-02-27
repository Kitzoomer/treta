from __future__ import annotations

import json
import logging
from typing import Any, Dict

from core.autonomy_policy_engine import AutonomyPolicyEngine
from core.domain.strategy_plan import StrategyPlan
from core.strategy_action_execution_layer import StrategyActionExecutionLayer
from core.strategy_decision_engine import StrategyDecisionEngine
from core.storage import Storage


class StrategyDecisionOrchestrator:
    def __init__(
        self,
        engine: StrategyDecisionEngine,
        storage: Storage,
        strategy_action_execution_layer: StrategyActionExecutionLayer,
        autonomy_policy_engine: AutonomyPolicyEngine | None = None,
    ):
        self._engine = engine
        self._storage = storage
        self._strategy_action_execution_layer = strategy_action_execution_layer
        self._autonomy_policy_engine = autonomy_policy_engine
        self._logger = logging.getLogger("treta.strategy.orchestrator")

    def _persist_plan(self, plan: StrategyPlan) -> None:
        context = plan.context_snapshot
        self._storage.create_decision_log(
            {
                "decision_type": "strategy_action",
                "entity_type": "portfolio",
                "entity_id": "global",
                "action_type": "recommend",
                "decision": "RECOMMEND",
                "risk_score": float(10 if plan.recommended_actions else 8),
                "policy_name": "StrategyDecisionEngine",
                "policy_snapshot_json": {
                    "rules": ["sales_scale_threshold", "stalled_launch_rule", "portfolio_activity_rule"],
                    "priority_level": context.get("priority_level"),
                },
                "inputs_json": {"launch_count": int(context.get("launch_count", 0) or 0)},
                "outputs_json": {
                    "decision_id": plan.decision_id,
                    "actions": plan.recommended_actions,
                    "risk_flags": context.get("risk_flags", []),
                    "autonomy_intent": plan.autonomy_intent,
                },
                "reason": f"Primary focus resolved to {context.get('primary_focus', 'stabilize')}.",
                "correlation_id": context.get("request_id"),
                "request_id": context.get("request_id"),
                "trace_id": context.get("trace_id"),
                "event_id": context.get("event_id"),
                "status": "recorded",
            }
        )

    def _materialize_actions(self, plan: StrategyPlan) -> None:
        context = plan.context_snapshot
        self._strategy_action_execution_layer.register_pending_actions(
            plan.recommended_actions,
            decision_id=plan.decision_id,
            event_id=context.get("event_id"),
            trace_id=context.get("trace_id"),
        )

    def _plan_result(self, plan: StrategyPlan, status: str) -> Dict[str, Any]:
        context = plan.context_snapshot
        return {
            "decision_id": plan.decision_id,
            "created_at": plan.created_at,
            "status": status,
            "priority_level": context.get("priority_level", "low"),
            "primary_focus": context.get("primary_focus", "stabilize"),
            "actions": plan.recommended_actions,
            "risk_flags": list(context.get("risk_flags", [])),
            "confidence": int(context.get("confidence", 8) or 8),
            "context": {
                "total_sales": context.get("total_sales", 0),
                "total_revenue": context.get("total_revenue", 0.0),
            },
            "plan": plan.to_dict(),
        }

    def run_decision_cycle(self, request_id: str | None = None, trace_id: str | None = None, event_id: str | None = None) -> Dict[str, Any]:
        plan = self._engine.decide(request_id=request_id, trace_id=trace_id, event_id=event_id)

        if self._storage.is_decision_processed(plan.decision_id):
            return self._plan_result(plan, status="duplicate")

        self._persist_plan(plan)
        self._materialize_actions(plan)

        if plan.autonomy_intent.get("should_execute") and self._autonomy_policy_engine is not None:
            try:
                self._autonomy_policy_engine.apply(request_id=str(plan.context_snapshot.get("request_id") or ""))
            except Exception as exc:
                self._logger.exception("Failed to apply autonomy policy", extra={"decision_id": plan.decision_id, "error": str(exc)})

        self._storage.mark_decision_processed(
            decision_id=plan.decision_id,
            kind="strategy_decision",
            payload_json=json.dumps(plan.to_dict(), sort_keys=True),
            status="processed",
        )
        return self._plan_result(plan, status="executed")
