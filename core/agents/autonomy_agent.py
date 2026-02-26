from __future__ import annotations

from typing import Any

from core.agents.base_agent import BaseAgent
from core.autonomy_policy_engine import AutonomyPolicyEngine


class AutonomyAgent(BaseAgent):
    def __init__(self, autonomy_policy_engine: AutonomyPolicyEngine):
        super().__init__(
            name="autonomy_agent",
            role="Evalúa guardrails de autonomía para habilitar o bloquear ejecución.",
            allowed_tools=["autonomy_policy_engine.status"],
            task_type="policy",
        )
        self._autonomy_policy_engine = autonomy_policy_engine

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        del input_data
        return {
            "agent": self.name,
            "status": self._autonomy_policy_engine.status(),
        }
