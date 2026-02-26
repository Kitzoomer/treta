from __future__ import annotations

import json

import pytest

from core.coherence_check_engine import CoherenceCheckEngine
from core.output_validator import OutputValidator
from core.strategy_engine import StrategyEngine


class _StaticLaunchStore:
    def list(self):
        return []


class _AlwaysValidPlanner:
    def create_plan(self, objective: str, state_snapshot: str):
        return {
            "objective": objective,
            "steps": [
                {"id": "s1", "description": "Analizar", "type": "analysis", "requires_llm": False},
            ],
        }


class _TrackingExecutor:
    def __init__(self):
        self.called = False

    def execute_plan(self, plan):
        self.called = True
        return {"status": "completed", "results": [], "total_steps": 0, "completed_steps": 0, "objective": plan.get("objective", "")}


class _InvalidPlanner:
    def create_plan(self, objective: str, state_snapshot: str):
        return {"objective": objective, "steps": [{"id": "s1", "description": "", "type": "analysis", "requires_llm": False}]}


class _ExecutorMustNotRun:
    def execute_plan(self, plan):
        raise AssertionError("Executor should not be called for invalid plan")


def test_output_validator_rejects_empty_strings_and_missing_fields():
    validator = OutputValidator()

    parsed = validator.validate_json(json.dumps({"objective": "Grow", "steps": []}))
    validator.validate_required_fields(parsed, ["objective", "steps"])

    with pytest.raises(ValueError):
        validator.validate_required_fields(parsed, ["objective", "steps", "owner"])

    with pytest.raises(ValueError):
        validator.validate_non_empty_strings({"objective": "", "steps": []})


def test_coherence_check_engine_detects_drift_and_requires_human_review():
    engine = CoherenceCheckEngine()
    result = engine.evaluate(
        plan={
            "objective": "Expandir mercado internacional sin relación",
            "steps": [{"id": f"s{i}", "description": "x", "type": "action", "requires_llm": False} for i in range(10)],
        },
        snapshot="embudo urgente con conversion local",
    )

    assert result.is_coherent is False
    assert result.requires_human_review is True
    assert result.drastic_changes


def test_strategy_engine_blocks_incoherent_plan_and_marks_human_review():
    executor = _TrackingExecutor()
    engine = StrategyEngine(
        product_launch_store=_StaticLaunchStore(),
        strategic_planner_engine=_AlwaysValidPlanner(),
        strategic_executor_engine=executor,
    )

    output = engine.run_strategic_plan(
        objective="Pause campañas actuales",
        state_snapshot="embudo urgente con conversion local",
    )

    assert output["coherence"]["requires_human_review"] is True
    assert output["execution"]["status"] == "blocked_for_human_review"
    assert executor.called is False


def test_invalid_plan_is_not_executed():
    engine = StrategyEngine(
        product_launch_store=_StaticLaunchStore(),
        strategic_planner_engine=_InvalidPlanner(),
        strategic_executor_engine=_ExecutorMustNotRun(),
    )

    with pytest.raises(ValueError):
        engine.run_strategic_plan(objective="Grow", state_snapshot="stable")


def test_planner_structured_logging_includes_model_tokens_and_time(caplog):
    from core.model_policy_engine import ModelPolicyEngine
    from core.strategic_planner_engine import StrategicPlannerEngine

    class _PlannerGPT:
        def chat(self, messages, task_type="chat", model=None):
            return json.dumps(
                {
                    "objective": "Grow",
                    "steps": [
                        {"id": "s1", "description": "Analyze", "type": "analysis", "requires_llm": False},
                    ],
                }
            )

    planner = StrategicPlannerEngine(gpt_client_optional=_PlannerGPT(), model_policy_engine=ModelPolicyEngine())
    with caplog.at_level("INFO", logger="treta.strategy.planner"):
        planner.create_plan(objective="Grow", state_snapshot="stable")

    generated = [r for r in caplog.records if r.message == "Strategic planner plan generated"]
    assert generated
    record = generated[-1]
    assert getattr(record, "model")
    assert getattr(record, "tokens_estimated") >= 1
    assert getattr(record, "response_time_ms") >= 0
    assert getattr(record, "task_type") == "planning"
