from core.agent_orchestrator import AgentOrchestrator
from core.agents.autonomy_agent import AutonomyAgent
from core.agents.planner_agent import PlannerAgent
from core.agents.risk_agent import RiskAgent


class _PlannerEngineStub:
    def create_plan(self, objective: str, state_snapshot: str):
        return {"objective": objective, "steps": [{"id": "s1", "description": state_snapshot, "type": "analysis", "requires_llm": False}]}


class _RiskEngineStub:
    def evaluate(self, action):
        return {"risk_level": "low", "expected_impact_score": 8, "auto_executable": True}


class _AutonomyEngineStub:
    def apply(self, request_id=None):
        return [{"id": "a1", "request_id": request_id}]

    def status(self):
        return {"mode": "manual"}


class _GrowthAgentStub:
    def run(self, payload):
        assert payload == {}
        return {"agent": "growth_agent", "recommendations": {"product_actions": []}}


def test_agents_wrap_existing_engines():
    planner = PlannerAgent(strategic_planner_engine=_PlannerEngineStub())
    plan_payload = planner.run({"objective": "Grow", "state_snapshot": "Stable"})
    assert plan_payload["plan"]["objective"] == "Grow"
    assert plan_payload["prompt_version"] == "planner.v1"

    risk = RiskAgent(risk_evaluation_engine=_RiskEngineStub())
    risk_payload = risk.run({"actions": [{"id": "x"}]})
    assert risk_payload["evaluated_actions"][0]["risk_level"] == "low"
    assert risk_payload["prompt_version"] == "risk.v1"

    autonomy = AutonomyAgent(autonomy_policy_engine=_AutonomyEngineStub())
    status_payload = autonomy.run({"mode": "status"})
    assert status_payload["status"]["mode"] == "manual"


def test_orchestrator_enforces_explicit_flow():
    planner = PlannerAgent(strategic_planner_engine=_PlannerEngineStub())
    risk = RiskAgent(risk_evaluation_engine=_RiskEngineStub())
    autonomy = AutonomyAgent(autonomy_policy_engine=_AutonomyEngineStub())
    growth = _GrowthAgentStub()

    orchestrator = AgentOrchestrator(
        planner_agent=planner,
        risk_agent=risk,
        growth_agent=growth,
        autonomy_agent=autonomy,
    )

    result = orchestrator.run(
        {
            "objective": "Ship feature",
            "state_snapshot": "No blockers",
            "actions": [{"id": "act-1", "type": "scale"}],
            "autonomy_mode": "apply",
            "request_id": "req-1",
            "sensitive_shared_data": "must_not_flow",
        }
    )

    assert result["planner"]["plan"]["objective"] == "Ship feature"
    assert result["risk"]["evaluated_actions"][0]["id"] == "act-1"
    assert result["autonomy"]["executed_actions"][0]["request_id"] == "req-1"
    assert "sensitive_shared_data" not in str(result)
