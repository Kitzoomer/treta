from __future__ import annotations

from collections import deque
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Dict, List


ProductProposal = Dict[str, Any]


class ProductProposalStore:
    """In-memory bounded store for product proposals."""

    def __init__(self, capacity: int = 50, path: Path | None = None):
        self._path = path or Path("/data/product_proposals.json")
        self._items: deque[ProductProposal] = deque(self._load_items(), maxlen=capacity)

    def _load_items(self) -> List[ProductProposal]:
        if not self._path.exists():
            return []
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(list(self._items), indent=2), encoding="utf-8")

    def add(self, proposal: Dict[str, Any]) -> ProductProposal:
        item = dict(proposal)
        self._items.append(item)
        self._save()
        return deepcopy(item)

    def list(self) -> List[ProductProposal]:
        return deepcopy(list(reversed(self._items)))

    def get(self, proposal_id: str) -> ProductProposal | None:
        for item in self._items:
            if item.get("id") == proposal_id:
                return deepcopy(item)
        return None
