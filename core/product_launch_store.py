from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
import uuid

from core.execution_focus_engine import ExecutionFocusEngine
from core.launch_metrics import LaunchMetricsModule
from core.product_proposal_store import ProductProposalStore


ProductLaunch = Dict[str, Any]

logger = logging.getLogger(__name__)


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

    def _quarantine_corrupt_file(self, reason: Exception) -> None:
        corrupt_path = self._path.with_suffix(self._path.suffix + ".corrupt")
        try:
            self._path.replace(corrupt_path)
        except OSError:
            logger.warning("Failed to quarantine corrupt JSON store at %s: %s", self._path, reason)
            return
        logger.warning("Corrupt JSON store moved from %s to %s: %s", self._path, corrupt_path, reason)

    def _load_items(self) -> List[ProductLaunch]:
        if not self._path.exists():
            return []
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._quarantine_corrupt_file(exc)
            return []
        if not isinstance(loaded, list):
            self._quarantine_corrupt_file(ValueError("expected list"))
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
            "gumroad_product_id": None,
            "last_gumroad_sync_at": None,
            "last_gumroad_sale_id": None,
            "active_execution": bool(item.get("active_execution", False)),
        }

        product_name = item.get("product_name")
        if product_name is not None:
            normalized["product_name"] = str(product_name)

        gumroad_product_id = item.get("gumroad_product_id")
        if gumroad_product_id is not None:
            normalized["gumroad_product_id"] = str(gumroad_product_id)

        last_gumroad_sync_at = item.get("last_gumroad_sync_at")
        if last_gumroad_sync_at is not None:
            normalized["last_gumroad_sync_at"] = str(last_gumroad_sync_at)

        last_gumroad_sale_id = item.get("last_gumroad_sale_id")
        if last_gumroad_sale_id is not None:
            normalized["last_gumroad_sale_id"] = str(last_gumroad_sale_id)

        return normalized


    def _refresh_execution_focus(self) -> None:
        target_id = ExecutionFocusEngine.select_active(self._proposal_store._items, self._items)
        ExecutionFocusEngine.enforce_single_active(
            target_id,
            {"proposals": self._proposal_store._items, "launches": self._items},
        )

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
        self._refresh_execution_focus()
        self._save()
        return deepcopy(item)

    def mark_launched(self, launch_id: str) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")
        item["launched_at"] = self._now()
        item["status"] = "active"
        self._refresh_execution_focus()
        self._save()
        return deepcopy(item)

    def add_sale(self, launch_id: str, amount: float) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")
        item["metrics"] = LaunchMetricsModule.add_sale(item.get("metrics", {}), amount)
        self._save()
        return deepcopy(item)

    def add_sales_batch(self, launch_id: str, sales_count: int, revenue_delta: float) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")

        metrics = LaunchMetricsModule.normalize(item.get("metrics", {}))
        metrics["sales"] += max(0, int(sales_count))
        metrics["revenue"] = round(metrics["revenue"] + float(revenue_delta), 2)
        item["metrics"] = metrics
        self._save()
        return deepcopy(item)

    def link_gumroad_product(self, launch_id: str, gumroad_product_id: str) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")

        product_id = str(gumroad_product_id).strip()
        if not product_id:
            raise ValueError("missing_gumroad_product_id")

        item["gumroad_product_id"] = product_id
        self._save()
        return deepcopy(item)

    def update_gumroad_sync_state(
        self,
        launch_id: str,
        *,
        last_sync_at: str,
        last_sale_id: str | None,
    ) -> ProductLaunch:
        item = self._find(launch_id)
        if item is None:
            raise ValueError(f"launch not found: {launch_id}")

        item["last_gumroad_sync_at"] = str(last_sync_at)
        item["last_gumroad_sale_id"] = str(last_sale_id) if last_sale_id else None
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
        self._refresh_execution_focus()
        self._save()
        return deepcopy(item)
