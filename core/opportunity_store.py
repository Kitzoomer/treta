from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List
import uuid


Opportunity = Dict[str, Any]


class OpportunityStore:
    """In-memory bounded store for opportunities."""

    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, capacity: int = 50, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "opportunities.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: deque[Opportunity] = deque(self._load_items(), maxlen=capacity)

    def _load_items(self) -> List[Opportunity]:
        if not self._path.exists():
            return []
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(list(self._items), indent=2), encoding="utf-8")

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
        self._save()
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
                self._save()
                return deepcopy(item)
        return None

    def set_status(self, item_id: str, status: str) -> Opportunity | None:
        for item in self._items:
            if item.get("id") == item_id:
                item["status"] = status
                self._save()
                return deepcopy(item)
        return None
