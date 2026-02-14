from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any, Dict, List


ProductPlan = Dict[str, Any]


class ProductPlanStore:
    """In-memory bounded store for product plans."""

    def __init__(self, capacity: int = 50):
        self._items: deque[ProductPlan] = deque(maxlen=capacity)

    def add(self, plan: Dict[str, Any]) -> ProductPlan:
        item = dict(plan)
        self._items.append(item)
        return deepcopy(item)

    def list(self, limit: int = 10) -> List[ProductPlan]:
        if limit <= 0:
            return []
        items = list(reversed(self._items))[:limit]
        return deepcopy(items)

    def get(self, plan_id: str) -> ProductPlan | None:
        for item in self._items:
            if item.get("plan_id") == plan_id:
                return deepcopy(item)
        return None

    def get_by_proposal_id(self, proposal_id: str) -> ProductPlan | None:
        for item in reversed(self._items):
            if item.get("proposal_id") == proposal_id:
                return deepcopy(item)
        return None
