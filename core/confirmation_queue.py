from __future__ import annotations

from typing import Dict, List
import uuid


class ConfirmationQueue:
    """In-memory queue for action plans awaiting user confirmation."""

    def __init__(self):
        self._pending: Dict[str, dict] = {}

    def add(self, plan: dict):
        plan_id = plan.get("id") or str(uuid.uuid4())
        stored_plan = dict(plan)
        stored_plan["id"] = plan_id
        self._pending[plan_id] = stored_plan
        return stored_plan

    def list_pending(self) -> List[dict]:
        return list(self._pending.values())

    def approve(self, plan_id: str):
        return self._pending.pop(plan_id, None)

    def reject(self, plan_id: str):
        return self._pending.pop(plan_id, None)

