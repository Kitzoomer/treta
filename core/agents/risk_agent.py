from __future__ import annotations

from typing import Any

from core.agents.base_agent import BaseAgent
from core.risk_evaluation_engine import RiskEvaluationEngine


class RiskAgent(BaseAgent):
    def __init__(self, risk_evaluation_engine: RiskEvaluationEngine | None = None):
        super().__init__(
            name="risk_agent",
            role="Evalúa nivel de riesgo e impacto esperado por acción.",
            allowed_tools=["risk_evaluation_engine.evaluate"],
            task_type="deterministic",
        )
        self._risk_evaluation_engine = risk_evaluation_engine or RiskEvaluationEngine()

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        actions = input_data.get("actions") or []
        if not isinstance(actions, list):
            actions = []

        evaluated_actions = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            evaluated_actions.append({**action, **self._risk_evaluation_engine.evaluate(action)})

        return {
            "agent": self.name,
            "evaluated_actions": evaluated_actions,
        }
