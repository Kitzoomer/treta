from __future__ import annotations

from typing import Any, Dict

from core.agents.base_agent import BaseAgent
from core.autonomy_policy_engine import AutonomyPolicyEngine


class AutonomyAgent(BaseAgent):
    PROMPT_VERSION = "autonomy.v1"
    SYSTEM_PROMPT = "Eres AutonomyAgent. Aplica guardrails de autonomía y nunca excedas límites de política."

    def __init__(self, autonomy_policy_engine: AutonomyPolicyEngine):
        super().__init__(
            name="autonomy_agent",
            role_description="Aplica políticas de auto-ejecución y reporta estado operativo.",
            allowed_tools=["autonomy_policy_engine.apply", "autonomy_policy_engine.status"],
            model_type="policy",
        )
        self._autonomy_policy_engine = autonomy_policy_engine

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = str(input_data.get("request_id") or "").strip() or None
        mode = str(input_data.get("mode") or "status").strip().lower()

        if mode == "apply":
            payload: Dict[str, Any] = {"executed_actions": self._autonomy_policy_engine.apply(request_id=request_id)}
        else:
            payload = {"status": self._autonomy_policy_engine.status()}

        return {
            "agent": self.name,
            "prompt_version": self.PROMPT_VERSION,
            "system_prompt": self.SYSTEM_PROMPT,
            **payload,
        }
