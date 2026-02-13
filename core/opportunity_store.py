from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid


Opportunity = Dict[str, Any]


class OpportunityStore:
    """In-memory bounded store for opportunities."""

    def __init__(self, capacity: int = 50):
        self._items: deque[Opportunity] = deque(maxlen=capacity)

    def add(
        self,
        *,
        source: str,
        title: str,
        summary: str,
        opportunity: Dict[str, Any],
        item_id: str | None = None,
    ) -> Opportunity:
        created = datetime.now(timezone.utc).isoformat()
        new_item: Opportunity = {
            "id": item_id or uuid.uuid4().hex[:8],
            "created_at": created,
            "source": str(source),
            "title": str(title),
            "summary": str(summary),
            "opportunity": dict(opportunity),
            "decision": None,
            "status": "new",
        }
        self._items.append(new_item)
        return deepcopy(new_item)

    def list(self, status: str | None = None) -> List[Opportunity]:
        items = list(self._items)
        if status is not None:
            items = [item for item in items if item.get("status") == status]
        return deepcopy(items)

    def get(self, item_id: str) -> Opportunity | None:
        for item in self._items:
            if item.get("id") == item_id:
                return deepcopy(item)
        return None

    def set_decision(self, item_id: str, decision: Dict[str, Any]) -> Opportunity | None:
        for item in self._items:
            if item.get("id") == item_id:
                item["decision"] = dict(decision)
                item["status"] = "evaluated"
                return deepcopy(item)
        return None

    def set_status(self, item_id: str, status: str) -> Opportunity | None:
        for item in self._items:
            if item.get("id") == item_id:
                item["status"] = status
                return deepcopy(item)
        return None
