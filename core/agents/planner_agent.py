from __future__ import annotations

from typing import Any

from core.agents.base_agent import BaseAgent
from core.strategic_planner_engine import StrategicPlannerEngine


class PlannerAgent(BaseAgent):
    def __init__(self, strategic_planner_engine: StrategicPlannerEngine | None = None):
        super().__init__(
            name="planner_agent",
            role="Construye planes estratégicos accionables con salida JSON validada.",
            allowed_tools=["strategic_planner_engine.create_plan"],
            task_type="planning",
        )
        self._strategic_planner_engine = strategic_planner_engine or StrategicPlannerEngine()

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        objective = str(input_data.get("objective") or "").strip()
        state_snapshot = str(input_data.get("state_snapshot") or "").strip()
        plan = self._strategic_planner_engine.create_plan(objective=objective, state_snapshot=state_snapshot)
        return {
            "agent": self.name,
            "plan": plan,
        }
