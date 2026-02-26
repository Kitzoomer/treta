from core.agent_orchestrator import AgentOrchestrator
from core.agents.autonomy_agent import AutonomyAgent
from core.agents.base_agent import BaseAgent
from core.agents.planner_agent import PlannerAgent
from core.agents.risk_agent import RiskAgent


class _PlannerEngineStub:
    def create_plan(self, objective: str, state_snapshot: str):
        return {
            "objective": objective,
            "steps": [{"id": "s1", "description": state_snapshot, "type": "analysis", "requires_llm": False}],
        }


class _RiskEngineStub:
    def evaluate(self, action):
        return {"risk_level": "low", "expected_impact_score": 8, "auto_executable": True}


class _AutonomyEngineStub:
    def status(self):
        return {"mode": "manual"}


def test_base_agent_contract_fields_are_exposed():
    class _ConcreteAgent(BaseAgent):
        def run(self, input_data):
            return input_data

    agent = _ConcreteAgent(name="x", role="planner", allowed_tools=["tool.run"], task_type="planning")
    assert agent.name == "x"
    assert agent.role == "planner"
    assert agent.allowed_tools == ["tool.run"]
    assert agent.task_type == "planning"


def test_agents_wrap_existing_engines():
    planner = PlannerAgent(strategic_planner_engine=_PlannerEngineStub())
    plan_payload = planner.run({"objective": "Grow", "state_snapshot": "Stable"})
    assert plan_payload["plan"]["objective"] == "Grow"

    risk = RiskAgent(risk_evaluation_engine=_RiskEngineStub())
    risk_payload = risk.run({"actions": [{"id": "x"}]})
    assert risk_payload["evaluated_actions"][0]["risk_level"] == "low"

    autonomy = AutonomyAgent(autonomy_policy_engine=_AutonomyEngineStub())
    status_payload = autonomy.run({"mode": "status"})
    assert status_payload["status"]["mode"] == "manual"


def test_orchestrator_runs_decide_risk_gate_propose_without_execution():
    planner = PlannerAgent(strategic_planner_engine=_PlannerEngineStub())
    risk = RiskAgent(risk_evaluation_engine=_RiskEngineStub())
    autonomy = AutonomyAgent(autonomy_policy_engine=_AutonomyEngineStub())

    orchestrator = AgentOrchestrator(
        planner_agent=planner,
        risk_agent=risk,
        autonomy_agent=autonomy,
    )

    result = orchestrator.run_cycle(
        {
            "objective": "Ship feature",
            "state_snapshot": "No blockers",
            "actions": [{"id": "act-1", "type": "scale"}],
            "sensitive_shared_data": "must_not_flow",
        }
    )

    assert result["decide"]["plan"]["objective"] == "Ship feature"
    assert result["risk"]["evaluated_actions"][0]["id"] == "act-1"
    assert result["gate"]["status"]["mode"] == "manual"
    assert result["propose"]["actions"][0]["status"] == "pending"
    assert result["propose"]["execution"] == "pending"
    assert "sensitive_shared_data" not in str(result)
