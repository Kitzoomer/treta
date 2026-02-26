from __future__ import annotations

import logging
from typing import Protocol


logger = logging.getLogger("treta.executors")


class ActionExecutor(Protocol):
    name: str
    supported_types: list[str]

    def execute(self, action: dict, context: dict) -> dict:
        ...


class ActionExecutorRegistry:
    def __init__(self):
        self._by_type: dict[str, ActionExecutor] = {}

    def register(self, executor: ActionExecutor) -> None:
        for action_type in executor.supported_types:
            self._by_type[str(action_type)] = executor

    def get_executor_for(self, action_type: str) -> ActionExecutor | None:
        return self._by_type.get(str(action_type))

    def execute(self, action: dict, context: dict) -> tuple[str, str, dict]:
        action_type = str(action.get("type") or "")
        executor = self.get_executor_for(action_type)
        if executor is None:
            logger.warning("No executor found for action type", extra={"action_type": action_type, "action_id": action.get("id")})
            return "skipped", "none", {"reason": f"no_executor_for:{action_type}"}
        output = executor.execute(action, context)
        return "success", executor.name, output
