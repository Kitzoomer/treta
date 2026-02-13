from __future__ import annotations

from datetime import datetime
from typing import Dict, List
import uuid


class ConfirmationQueue:
    """In-memory queue for action plans awaiting user confirmation."""

    def __init__(self):
        self._plans: Dict[str, dict] = {}

    def add(self, plan: dict) -> str:
        plan_id = str(uuid.uuid4())
        queued_plan = {
            "id": plan_id,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "plan": dict(plan),
        }
        self._plans[plan_id] = queued_plan
        return plan_id

    def list_pending(self) -> List[dict]:
        pending = [item for item in self._plans.values() if item["status"] == "pending"]
        pending.sort(key=lambda item: item["created_at"])
        return pending[-20:]

    def approve(self, plan_id: str) -> dict | None:
        queued_plan = self._plans.get(plan_id)
        if queued_plan is None or queued_plan["status"] != "pending":
            return None

        queued_plan["status"] = "approved"
        return queued_plan

    def reject(self, plan_id: str) -> dict | None:
        queued_plan = self._plans.get(plan_id)
        if queued_plan is None or queued_plan["status"] != "pending":
            return None

        queued_plan["status"] = "rejected"
        return queued_plan
