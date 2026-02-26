from __future__ import annotations

from typing import Any, Dict, List

from core.agents.base_agent import BaseAgent
from core.risk_evaluation_engine import RiskEvaluationEngine


class RiskAgent(BaseAgent):
    PROMPT_VERSION = "risk.v1"
    SYSTEM_PROMPT = "Eres RiskAgent. Evalúa riesgo por acción con reglas determinísticas y salida estructurada."

    def __init__(self, risk_evaluation_engine: RiskEvaluationEngine | None = None):
        super().__init__(
            name="risk_agent",
            role_description="Evalúa nivel de riesgo e impacto esperado por acción.",
            allowed_tools=["risk_evaluation_engine.evaluate"],
            model_type="deterministic",
        )
        self._risk_evaluation_engine = risk_evaluation_engine or RiskEvaluationEngine()

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        actions = input_data.get("actions") or []
        if not isinstance(actions, list):
            actions = []

        evaluated_actions: List[Dict[str, Any]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            evaluated_actions.append({**action, **self._risk_evaluation_engine.evaluate(action)})

        return {
            "agent": self.name,
            "prompt_version": self.PROMPT_VERSION,
            "system_prompt": self.SYSTEM_PROMPT,
            "evaluated_actions": evaluated_actions,
        }
