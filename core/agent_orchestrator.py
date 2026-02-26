from __future__ import annotations

from typing import Any, Dict

from core.agents.autonomy_agent import AutonomyAgent
from core.agents.growth_agent import GrowthAgent
from core.agents.planner_agent import PlannerAgent
from core.agents.risk_agent import RiskAgent


class AgentOrchestrator:
    """Coordinates agent execution order and enforces explicit data flow boundaries."""

    def __init__(
        self,
        planner_agent: PlannerAgent,
        risk_agent: RiskAgent,
        growth_agent: GrowthAgent,
        autonomy_agent: AutonomyAgent,
    ):
        self._planner_agent = planner_agent
        self._risk_agent = risk_agent
        self._growth_agent = growth_agent
        self._autonomy_agent = autonomy_agent

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        objective = str(input_data.get("objective") or "").strip()
        state_snapshot = str(input_data.get("state_snapshot") or "").strip()
        actions = input_data.get("actions") or []
        autonomy_mode = str(input_data.get("autonomy_mode") or "status").strip().lower()
        request_id = str(input_data.get("request_id") or "").strip()

        planner_output = self._planner_agent.run(
            {
                "objective": objective,
                "state_snapshot": state_snapshot,
            }
        )

        risk_output = self._risk_agent.run(
            {
                "actions": actions,
            }
        )

        growth_output = self._growth_agent.run({})

        autonomy_output = self._autonomy_agent.run(
            {
                "mode": autonomy_mode,
                "request_id": request_id,
            }
        )

        return {
            "planner": planner_output,
            "risk": risk_output,
            "growth": growth_output,
            "autonomy": autonomy_output,
        }
