from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List


ProductProposal = Dict[str, Any]


class ProductProposalStore:
    """In-memory bounded store for product proposals."""

    _DEFAULT_DATA_DIR = "./.treta_data"
    _ALLOWED_STATUSES = {
        "draft",
        "approved",
        "building",
        "ready_to_launch",
        "ready_for_review",
        "launched",
        "rejected",
        "archived",
    }
    _TRANSITIONS = {
        "draft": {"approved", "rejected"},
        "approved": {"building", "archived"},
        "building": {"ready_to_launch"},
        "ready_to_launch": {"ready_for_review"},
        "ready_for_review": {"launched"},
        "launched": {"archived"},
        "rejected": {"archived"},
        "archived": set(),
    }

    def __init__(self, capacity: int = 50, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "product_proposals.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: deque[ProductProposal] = deque(self._load_items(), maxlen=capacity)

    def _load_items(self) -> List[ProductProposal]:
        if not self._path.exists():
            return []
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            return []
        return [self._normalize_item(dict(item)) for item in loaded if isinstance(item, dict)]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_item(self, item: ProductProposal) -> ProductProposal:
        status = str(item.get("status", "draft")).strip() or "draft"
        if status not in self._ALLOWED_STATUSES:
            status = "draft"
        item["status"] = status
        item["updated_at"] = str(item.get("updated_at") or item.get("created_at") or self._now())
        return item

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(list(self._items), indent=2), encoding="utf-8")

    def add(self, proposal: Dict[str, Any]) -> ProductProposal:
        item = self._normalize_item(dict(proposal))
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

    def transition_status(self, proposal_id: str, new_status: str) -> ProductProposal:
        target_status = str(new_status).strip()
        if target_status not in self._ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {new_status}")

        for item in self._items:
            if item.get("id") != proposal_id:
                continue

            current_status = str(item.get("status", "draft"))
            allowed_targets = self._TRANSITIONS.get(current_status, set())
            if target_status not in allowed_targets:
                raise ValueError(f"invalid transition: {current_status} -> {target_status}")

            item["status"] = target_status
            item["updated_at"] = self._now()
            self._save()
            return deepcopy(item)

        raise ValueError(f"proposal not found: {proposal_id}")
