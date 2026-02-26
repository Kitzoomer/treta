from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Base contract for all internal agents in the agent layer."""

    def __init__(
        self,
        name: str,
        role: str | None = None,
        allowed_tools: list[str] | None = None,
        task_type: str | None = None,
        *,
        role_description: str | None = None,
        model_type: str | None = None,
    ):
        resolved_role = role if role is not None else role_description or ""
        resolved_task_type = task_type if task_type is not None else model_type or ""

        self.name = str(name)
        self.role = str(resolved_role)
        self.allowed_tools = list(allowed_tools or [])
        self.task_type = str(resolved_task_type)

        # Backwards-compatible aliases.
        self.role_description = self.role
        self.model_type = self.task_type

    @abstractmethod
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent task and return structured output."""
        raise NotImplementedError
