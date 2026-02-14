from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any, Dict, List


ProductProposal = Dict[str, Any]


class ProductProposalStore:
    """In-memory bounded store for product proposals."""

    def __init__(self, capacity: int = 50):
        self._items: deque[ProductProposal] = deque(maxlen=capacity)

    def add(self, proposal: Dict[str, Any]) -> ProductProposal:
        item = dict(proposal)
        self._items.append(item)
        return deepcopy(item)

    def list(self) -> List[ProductProposal]:
        return deepcopy(list(reversed(self._items)))

    def get(self, proposal_id: str) -> ProductProposal | None:
        for item in self._items:
            if item.get("id") == proposal_id:
                return deepcopy(item)
        return None
