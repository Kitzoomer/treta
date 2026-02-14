from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List
import uuid

from core.launch_metrics import LaunchMetricsModule
from core.product_proposal_store import ProductProposalStore


ProductLaunch = Dict[str, Any]


class ProductLaunchStore:
    """Persistent bounded store for product launches."""

    _DEFAULT_DATA_DIR = "./.treta_data"
    _ALLOWED_STATUSES = {"draft", "active", "paused", "archived"}
    _TRANSITIONS = {
        "draft": {"active", "archived"},
        "active": {"paused", "archived"},
        "paused": {"active", "archived"},
        "archived": set(),
    }

    def __init__(
        self,
        proposal_store: ProductProposalStore | None = None,
        capacity: int = 100,
        path: Path | None = None,
    ):
        self._proposal_store = proposal_store or ProductProposalStore()
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "product_launches.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: deque[ProductLaunch] = deque(self._load_items(), maxlen=capacity)

    def _load_items(self) -> List[ProductLaunch]:
        if not self._path.exists():
            return []
        loaded = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            return []
        return [self._normalize_item(dict(item)) for item in loaded if isinstance(item, dict)]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(list(self._items), indent=2), encoding="utf-8")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_item(self, item: ProductLaunch) -> ProductLaunch:
        status = str(item.get("status", "draft")).strip() or "draft"
        if status not in self._ALLOWED_STATUSES:
            status = "draft"

        created_at = str(item.get("created_at") or self._now())
        launched_at = item.get("launched_at")
        if launched_at is not None:
            launched_at = str(launched_at)

        normalized = {
            "id": str(item.get("id") or f"launch-{uuid.uuid4().hex[:12]}"),
            "proposal_id": str(item.get("proposal_id") or ""),
            "created_at": created_at,
            "launched_at": launched_at,
            "status": status,
            "metrics": LaunchMetricsModule.normalize(item.get("metrics")),
        }

        product_name = item.get("product_name")
        if product_name is not None:
            normalized["product_name"] = str(product_name)

        return normalized

    def _find(self, launch_id: str) -> ProductLaunch | None:
        for item in self._items:
            if item.get("id") == launch_id:
                return item
        return None

    def add_from_proposal(self, proposal_id: str) -> ProductLaunch:
        proposal = self._proposal_store.get(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")

        existing = self.get_by_proposal_id(proposal_id)
        if existing is not None:
            return existing

        item = self._normalize_item(
            {
                "id": f"launch-{uuid.uuid4().hex[:12]}",
                "proposal_id": proposal_id,
                "created_at": self._now(),
                "launched_at": None,
                "status": "draft",
                "metrics": LaunchMetricsModule.default(),
                "product_name": proposal.get("product_name"),
            }
        )
        self._items.append(item)
        self._save()
        return deepcopy(item)

    def mark_launched(self, launch_id: str) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")
        item["launched_at"] = self._now()
        item["status"] = "active"
        self._save()
        return deepcopy(item)

    def add_sale(self, launch_id: str, amount: float) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")
        item["metrics"] = LaunchMetricsModule.add_sale(item.get("metrics", {}), amount)
        self._save()
        return deepcopy(item)

    def list(self) -> List[ProductLaunch]:
        return deepcopy(list(reversed(self._items)))

    def get(self, launch_id: str) -> ProductLaunch | None:
        item = self._find(launch_id)
        if item is None:
            return None
        return deepcopy(item)

    def get_by_proposal_id(self, proposal_id: str) -> ProductLaunch | None:
        for item in reversed(self._items):
            if item.get("proposal_id") == proposal_id:
                return deepcopy(item)
        return None

    def transition_status(self, launch_id: str, new_status: str) -> ProductLaunch:
        target_status = str(new_status).strip()
        if target_status not in self._ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {new_status}")

        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")

        current_status = str(item.get("status", "draft"))
        allowed = self._TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ValueError(f"invalid transition: {current_status} -> {target_status}")

        item["status"] = target_status
        self._save()
        return deepcopy(item)
