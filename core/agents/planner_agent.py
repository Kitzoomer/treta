from __future__ import annotations

from typing import Any, Dict

from core.agents.base_agent import BaseAgent
from core.strategic_planner_engine import StrategicPlannerEngine


class PlannerAgent(BaseAgent):
    PROMPT_VERSION = "planner.v1"
    SYSTEM_PROMPT = (
        "Eres PlannerAgent. Genera un plan estratégico estricto con pasos analysis/action/validation "
        "en JSON válido y sin campos extra."
    )

    def __init__(self, strategic_planner_engine: StrategicPlannerEngine | None = None):
        super().__init__(
            name="planner_agent",
            role_description="Construye planes estratégicos accionables con salida JSON validada.",
            allowed_tools=["strategic_planner_engine.create_plan"],
            model_type="planning",
        )
        self._strategic_planner_engine = strategic_planner_engine or StrategicPlannerEngine()

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        objective = str(input_data.get("objective") or "").strip()
        state_snapshot = str(input_data.get("state_snapshot") or "").strip()
        plan = self._strategic_planner_engine.create_plan(objective=objective, state_snapshot=state_snapshot)
        return {
            "agent": self.name,
            "prompt_version": self.PROMPT_VERSION,
            "system_prompt": self.SYSTEM_PROMPT,
            "plan": plan,
        }
