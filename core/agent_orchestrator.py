from __future__ import annotations

from typing import Any

from core.agents.autonomy_agent import AutonomyAgent
from core.agents.planner_agent import PlannerAgent
from core.agents.risk_agent import RiskAgent


class AgentOrchestrator:
    """Minimal orchestration pipeline: decide -> risk -> gate -> propose."""

    def __init__(
        self,
        planner_agent: PlannerAgent,
        risk_agent: RiskAgent,
        autonomy_agent: AutonomyAgent,
    ):
        self._planner_agent = planner_agent
        self._risk_agent = risk_agent
        self._autonomy_agent = autonomy_agent

    def run_cycle(self, state: dict[str, Any]) -> dict[str, Any]:
        objective = str(state.get("objective") or "").strip()
        state_snapshot = str(state.get("state_snapshot") or "").strip()
        actions = state.get("actions") or []

        decide_output = self._planner_agent.run(
            {
                "objective": objective,
                "state_snapshot": state_snapshot,
            }
        )
        risk_output = self._risk_agent.run({"actions": actions})
        gate_output = self._autonomy_agent.run({})

        proposed_actions = [
            {
                **action,
                "status": "pending",
            }
            for action in risk_output.get("evaluated_actions", [])
            if isinstance(action, dict)
        ]

        return {
            "decide": decide_output,
            "risk": risk_output,
            "gate": gate_output,
            "propose": {
                "actions": proposed_actions,
                "execution": "pending",
            },
        }

    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible alias."""
        return self.run_cycle(input_data)
