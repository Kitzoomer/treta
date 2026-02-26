from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from core.model_policy_engine import ModelPolicyEngine
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.strategic_executor_engine import StrategicExecutorEngine
from core.strategic_planner_engine import StrategicPlannerEngine, StrategicPlannerError
from core.strategy_engine import StrategyEngine


class _FakePlannerGPT:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def chat(self, messages, task_type="chat", model=None):
        self.calls.append({"task_type": task_type, "model": model, "messages": messages})
        return json.dumps(
            {
                "objective": "Grow monthly recurring revenue",
                "steps": [
                    {
                        "id": "p-1",
                        "description": "Analyze current launch funnel",
                        "type": "analysis",
                        "requires_llm": False,
                    },
                    {
                        "id": "p-2",
                        "description": "Draft optimization hypothesis",
                        "type": "action",
                        "requires_llm": True,
                    },
                    {
                        "id": "p-3",
                        "description": "Validate expected impact",
                        "type": "validation",
                        "requires_llm": False,
                    },
                ],
            }
        )


class _FakeExecutorGPT:
    def __init__(self):
        self.calls: list[dict[str, object]] = []

    def chat(self, messages, task_type="chat", model=None):
        self.calls.append({"task_type": task_type, "model": model, "messages": messages})
        return "LLM execution completed"


class _RetryPlannerGPT:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, task_type="chat", model=None, response_format=None):
        del messages, task_type, model, response_format
        self.calls += 1
        if self.calls == 1:
            return "{invalid json"
        return json.dumps(
            {
                "objective": "Grow monthly recurring revenue",
                "steps": [
                    {
                        "id": "p-1",
                        "description": "Analyze current launch funnel",
                        "type": "analysis",
                        "requires_llm": False,
                    }
                ],
            }
        )


class _AlwaysInvalidPlannerGPT:
    def chat(self, messages, task_type="chat", model=None, response_format=None):
        del messages, task_type, model, response_format
        return "not json"


def _seed_store(root: Path) -> ProductLaunchStore:
    proposals = ProductProposalStore(path=root / "product_proposals.json")
    launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")

    proposals.add({"id": "proposal-1", "product_name": "Creator Growth Kit"})
    launch = launches.add_from_proposal("proposal-1")
    launches.add_sale(launch["id"], 25)
    launches.add_sale(launch["id"], 25)

    raw = json.loads((root / "product_launches.json").read_text(encoding="utf-8"))
    raw[0]["created_at"] = datetime(2025, 1, 9, tzinfo=timezone.utc).isoformat()
    (root / "product_launches.json").write_text(json.dumps(raw), encoding="utf-8")

    return ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")


def test_strategic_planner_engine_creates_valid_json_with_planning_model():
    fake_gpt = _FakePlannerGPT()
    planner = StrategicPlannerEngine(gpt_client_optional=fake_gpt, model_policy_engine=ModelPolicyEngine())

    plan = planner.create_plan(
        objective="Grow monthly recurring revenue",
        state_snapshot="1 launch active, conversion drop in week 2",
    )

    assert plan["objective"] == "Grow monthly recurring revenue"
    assert isinstance(plan["steps"], list)
    assert len(plan["steps"]) == 3
    assert fake_gpt.calls[0]["task_type"] == "planning"
    assert fake_gpt.calls[0]["model"] == "gpt-4o"


def test_strategic_executor_engine_runs_steps_and_uses_execution_model_for_llm_steps():
    fake_gpt = _FakeExecutorGPT()
    executor = StrategicExecutorEngine(gpt_client_optional=fake_gpt, model_policy_engine=ModelPolicyEngine())

    result = executor.execute_plan(
        {
            "objective": "Grow monthly recurring revenue",
            "steps": [
                {"id": "s1", "description": "Analyze baseline metrics", "type": "analysis", "requires_llm": False},
                {"id": "s2", "description": "Generate optimization action", "type": "action", "requires_llm": True},
                {"id": "s3", "description": "Validate expected uplift", "type": "validation", "requires_llm": False},
            ],
        }
    )

    assert result["status"] == "completed"
    assert result["completed_steps"] == 3
    assert result["results"][0]["mode"] == "internal"
    assert result["results"][1]["mode"] == "llm"
    assert result["results"][2]["mode"] == "internal"
    assert fake_gpt.calls[0]["task_type"] == "execution"
    assert fake_gpt.calls[0]["model"] == "gpt-4o-mini"


def test_strategy_engine_integrates_planner_then_executor():
    with TemporaryDirectory() as tmp_dir:
        launches = _seed_store(Path(tmp_dir))

        planner_gpt = _FakePlannerGPT()
        executor_gpt = _FakeExecutorGPT()
        planner = StrategicPlannerEngine(gpt_client_optional=planner_gpt, model_policy_engine=ModelPolicyEngine())
        executor = StrategicExecutorEngine(gpt_client_optional=executor_gpt, model_policy_engine=ModelPolicyEngine())

        engine = StrategyEngine(
            product_launch_store=launches,
            strategic_planner_engine=planner,
            strategic_executor_engine=executor,
        )

        output = engine.run_strategic_plan(
            objective="Grow monthly recurring revenue",
            state_snapshot="2 sales this week, no action backlog",
        )

        assert "plan" in output
        assert "execution" in output
        assert output["plan"]["objective"] == "Grow monthly recurring revenue"
        assert output["execution"]["status"] == "completed"
        assert planner_gpt.calls[0]["task_type"] == "planning"
        assert executor_gpt.calls[0]["task_type"] == "execution"


def test_strategic_planner_engine_repairs_invalid_first_attempt():
    planner = StrategicPlannerEngine(gpt_client_optional=_RetryPlannerGPT(), model_policy_engine=ModelPolicyEngine())

    plan = planner.create_plan(objective="Grow monthly recurring revenue", state_snapshot="baseline stable")

    assert plan["objective"] == "Grow monthly recurring revenue"
    assert len(plan["steps"]) == 1


def test_strategic_planner_engine_raises_structured_error_after_retries():
    planner = StrategicPlannerEngine(gpt_client_optional=_AlwaysInvalidPlannerGPT(), model_policy_engine=ModelPolicyEngine())

    try:
        planner.create_plan(objective="Grow monthly recurring revenue", state_snapshot="baseline stable")
        raise AssertionError("Expected StrategicPlannerError")
    except StrategicPlannerError as exc:
        assert exc.payload["code"] == "STRATEGIC_PLANNER_JSON_FAILURE"
        assert exc.payload["trace"]["model"] == "gpt-4o"
        assert len(exc.payload["trace"]["attempts"]) == 2
