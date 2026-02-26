from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseAgent(ABC):
    """Base contract for all internal agents in the agent layer."""

    def __init__(
        self,
        name: str,
        role_description: str,
        allowed_tools: List[str],
        model_type: str,
    ):
        self.name = str(name)
        self.role_description = str(role_description)
        self.allowed_tools = list(allowed_tools)
        self.model_type = str(model_type)

    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent task and return structured output."""
        raise NotImplementedError
