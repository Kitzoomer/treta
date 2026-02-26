from __future__ import annotations

import os
from typing import Literal

TaskType = Literal["chat", "planning", "summarize", "eval", "execution", "tts"]


class ModelPolicyEngine:
    _MODEL_ENV_BY_TASK: dict[TaskType, str] = {
        "chat": "TRETA_MODEL_CHAT",
        "planning": "TRETA_MODEL_PLANNING",
        "summarize": "TRETA_MODEL_SUMMARIZE",
        "eval": "TRETA_MODEL_EVAL",
        "execution": "TRETA_MODEL_EXECUTION",
        "tts": "TRETA_MODEL_TTS",
    }

    _DEFAULT_MODEL_BY_TASK: dict[TaskType, str] = {
        "chat": "gpt-4o-mini",
        "planning": "gpt-4o-mini",
        "summarize": "gpt-4o-mini",
        "eval": "gpt-4o-mini",
        "execution": "gpt-4o-mini",
        "tts": "gpt-4o-mini-tts",
    }

    def get_model(self, task_type: TaskType) -> str:
        env_name = self._MODEL_ENV_BY_TASK.get(task_type)
        default_model = self._DEFAULT_MODEL_BY_TASK[task_type]

        if not env_name:
            return default_model

        configured_model = os.getenv(env_name, "").strip()
        return configured_model or default_model

