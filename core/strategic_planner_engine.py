from __future__ import annotations

import json
import logging
import time
from typing import Any

from core.model_policy_engine import ModelPolicyEngine
from core.output_validator import OutputValidator


class StrategicPlannerEngine:
    """Builds a strict strategic plan JSON from an objective and state snapshot."""

    def __init__(self, gpt_client_optional: Any = None, model_policy_engine: ModelPolicyEngine | None = None):
        self._gpt_client = gpt_client_optional
        self._model_policy_engine = model_policy_engine or ModelPolicyEngine()
        self._output_validator = OutputValidator()
        self._logger = logging.getLogger("treta.strategy.planner")

    def _fallback_plan(self, objective: str, state_snapshot: str) -> dict[str, Any]:
        del state_snapshot
        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "description": "Analizar el estado actual y definir prioridades inmediatas.",
                    "type": "analysis",
                    "requires_llm": False,
                },
                {
                    "id": "step-2",
                    "description": "Ejecutar la acción prioritaria con menor riesgo operativo.",
                    "type": "action",
                    "requires_llm": True,
                },
                {
                    "id": "step-3",
                    "description": "Validar resultado y documentar próximos ajustes.",
                    "type": "validation",
                    "requires_llm": False,
                },
            ],
        }

    def _validate_plan(self, plan: Any) -> dict[str, Any]:
        if not isinstance(plan, dict):
            raise ValueError("Plan must be a JSON object")

        allowed_top_level_keys = {"objective", "steps"}
        if set(plan.keys()) != allowed_top_level_keys:
            raise ValueError("Plan must contain only 'objective' and 'steps'")

        objective = plan.get("objective")
        if not isinstance(objective, str):
            raise ValueError("Plan objective must be a string")

        steps = plan.get("steps")
        if not isinstance(steps, list):
            raise ValueError("Plan steps must be a list")

        allowed_step_types = {"analysis", "action", "validation"}
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Each step must be a JSON object")
            if set(step.keys()) != {"id", "description", "type", "requires_llm"}:
                raise ValueError("Each step must contain only id, description, type, requires_llm")

            if not isinstance(step.get("id"), str) or not step["id"].strip():
                raise ValueError("Step id must be a non-empty string")
            if not isinstance(step.get("description"), str) or not step["description"].strip():
                raise ValueError("Step description must be a non-empty string")
            if step.get("type") not in allowed_step_types:
                raise ValueError("Step type must be one of analysis|action|validation")
            if not isinstance(step.get("requires_llm"), bool):
                raise ValueError("Step requires_llm must be a boolean")

        return plan

    def create_plan(self, objective: str, state_snapshot: str) -> dict[str, Any]:
        normalized_objective = str(objective or "").strip()
        normalized_snapshot = str(state_snapshot or "").strip()

        if not normalized_objective:
            normalized_objective = "Definir siguiente mejor acción estratégica"

        if self._gpt_client is None or not hasattr(self._gpt_client, "chat"):
            fallback = self._fallback_plan(normalized_objective, normalized_snapshot)
            self._logger.info("Strategic planner fallback used", extra={"objective": normalized_objective, "mode": "fallback"})
            return self._validate_plan(fallback)

        schema = {
            "objective": "string",
            "steps": [
                {
                    "id": "string",
                    "description": "string",
                    "type": "analysis | action | validation",
                    "requires_llm": "boolean",
                }
            ],
        }

        prompt = (
            "Devuelve EXCLUSIVAMENTE JSON válido (sin markdown) con el schema exacto solicitado. "
            "No agregues campos extra y usa requires_llm=true solo cuando sea necesario LLM."
        )

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"objective: {normalized_objective}\n"
                    f"state_snapshot: {normalized_snapshot}\n"
                    f"schema: {json.dumps(schema, ensure_ascii=False)}"
                ),
            },
        ]

        model_name = self._model_policy_engine.get_model(task_type="planning")
        started_at = time.perf_counter()
        self._logger.info(
            "Strategic planner creating plan",
            extra={"objective": normalized_objective, "model": model_name, "phase": "plan"},
        )
        try:
            raw = self._gpt_client.chat(messages=messages, task_type="planning", model=model_name)
            parsed = self._output_validator.validate_json(str(raw or "{}"))
            self._output_validator.validate_required_fields(parsed, ["objective", "steps"])
            self._output_validator.validate_schema(parsed, {"objective": "string", "steps": []})
            self._output_validator.validate_non_empty_strings(parsed)
            validated = self._validate_plan(parsed)
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            estimated_tokens = max(len(str(raw or "")) // 4, 1)
            self._logger.info(
                "Strategic planner plan generated",
                extra={
                    "objective": normalized_objective,
                    "model": model_name,
                    "steps": len(validated.get("steps", [])),
                    "phase": "plan",
                    "task_type": "planning",
                    "tokens_estimated": estimated_tokens,
                    "response_time_ms": elapsed_ms,
                },
            )
            return validated
        except Exception as exc:
            self._logger.warning(
                "Strategic planner failed, using fallback",
                extra={"objective": normalized_objective, "model": model_name, "phase": "plan", "error": str(exc)},
            )
            return self._validate_plan(self._fallback_plan(normalized_objective, normalized_snapshot))
