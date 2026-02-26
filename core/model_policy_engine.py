from __future__ import annotations


class ModelPolicyEngine:
    def __init__(self, policy: dict[str, str] | None = None):
        self._policy = policy or {
            "planning": "gpt-4o",
            "execution": "gpt-4o-mini",
            "evaluation": "gpt-4o-mini",
            "chat": "gpt-4o-mini",
        }

    def get_model(self, task_type: str) -> str:
        normalized_task_type = str(task_type or "").strip().lower()
        return self._policy.get(normalized_task_type, self._policy["chat"])
