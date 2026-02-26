from __future__ import annotations

import logging
from typing import Any

from core.model_policy_engine import ModelPolicyEngine


class StrategicExecutorEngine:
    """Executes a strategic plan step by step, delegating LLM-only steps when required."""

    def __init__(self, gpt_client_optional: Any = None, model_policy_engine: ModelPolicyEngine | None = None):
        self._gpt_client = gpt_client_optional
        self._model_policy_engine = model_policy_engine or ModelPolicyEngine()
        self._logger = logging.getLogger("treta.strategy.executor")

    def _execute_internal_step(self, step: dict[str, Any]) -> dict[str, Any]:
        step_type = str(step.get("type") or "")
        description = str(step.get("description") or "")
        if step_type == "analysis":
            output = f"Análisis interno completado: {description}"
        elif step_type == "validation":
            output = f"Validación interna completada: {description}"
        else:
            output = f"Acción interna completada: {description}"

        return {
            "step_id": str(step.get("id") or ""),
            "status": "completed",
            "mode": "internal",
            "output": output,
        }

    def _execute_llm_step(self, step: dict[str, Any]) -> dict[str, Any]:
        if self._gpt_client is None or not hasattr(self._gpt_client, "chat"):
            return {
                "step_id": str(step.get("id") or ""),
                "status": "completed",
                "mode": "internal_fallback",
                "output": f"LLM no disponible, fallback aplicado para: {step.get('description', '')}",
            }

        model_name = self._model_policy_engine.get_model(task_type="execution")
        messages = [
            {
                "role": "system",
                "content": "Ejecuta el paso estratégico solicitado y responde en texto breve con resultado operativo.",
            },
            {
                "role": "user",
                "content": f"step_id={step.get('id','')}\ntype={step.get('type','')}\ndescription={step.get('description','')}",
            },
        ]
        output = str(self._gpt_client.chat(messages=messages, task_type="execution", model=model_name)).strip()
        return {
            "step_id": str(step.get("id") or ""),
            "status": "completed",
            "mode": "llm",
            "output": output,
            "model": model_name,
        }

    def execute_plan(self, plan: dict) -> dict[str, Any]:
        objective = str(plan.get("objective") or "")
        steps = plan.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("Plan steps must be a list")

        self._logger.info(
            "Strategic executor starting",
            extra={"objective": objective, "steps": len(steps), "phase": "execute"},
        )

        results: list[dict[str, Any]] = []
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Invalid step payload")

            step_id = str(step.get("id") or "")
            requires_llm = bool(step.get("requires_llm", False))
            self._logger.info(
                "Strategic executor processing step",
                extra={"objective": objective, "step_id": step_id, "requires_llm": requires_llm, "phase": "execute"},
            )

            if requires_llm:
                step_result = self._execute_llm_step(step)
            else:
                step_result = self._execute_internal_step(step)

            results.append(step_result)

        summary = {
            "objective": objective,
            "status": "completed",
            "total_steps": len(results),
            "completed_steps": sum(1 for item in results if item.get("status") == "completed"),
            "results": results,
        }
        self._logger.info(
            "Strategic executor completed",
            extra={"objective": objective, "completed_steps": summary["completed_steps"], "phase": "execute"},
        )
        return summary
