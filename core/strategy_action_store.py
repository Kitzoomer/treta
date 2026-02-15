from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from core.risk_evaluation_engine import RiskEvaluationEngine


StrategyAction = Dict[str, Any]


class StrategyActionStore:
    """Persistent bounded store for strategy actions requiring confirmation."""

    _DEFAULT_DATA_DIR = "./.treta_data"
    _ALLOWED_TYPES = {"scale", "review", "price_test", "new_product", "archive"}
    _ALLOWED_STATUSES = {"pending_confirmation", "executed", "auto_executed", "rejected"}

    def __init__(self, capacity: int = 200, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "strategy_actions.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._risk_evaluation_engine = RiskEvaluationEngine()
        self._items: deque[StrategyAction] = deque(self._load_items(), maxlen=capacity)

    def _load_items(self) -> List[StrategyAction]:
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

    def _next_id(self) -> str:
        max_index = 0
        for item in self._items:
            item_id = str(item.get("id", ""))
            if item_id.startswith("action-"):
                try:
                    max_index = max(max_index, int(item_id.replace("action-", "")))
                except ValueError:
                    continue
        return f"action-{max_index + 1:06d}"

    def _normalize_item(self, item: StrategyAction) -> StrategyAction:
        action_type = str(item.get("type") or "review")
        if action_type not in self._ALLOWED_TYPES:
            action_type = "review"

        status = str(item.get("status") or "pending_confirmation")
        if status not in self._ALLOWED_STATUSES:
            status = "pending_confirmation"

        sales = item.get("sales")
        try:
            normalized_sales = max(int(sales), 0) if sales is not None else None
        except (TypeError, ValueError):
            normalized_sales = None

        normalized = {
            "id": str(item.get("id") or self._next_id()),
            "type": action_type,
            "target_id": str(item.get("target_id") or ""),
            "reasoning": str(item.get("reasoning") or ""),
            "status": status,
            "created_at": str(item.get("created_at") or self._now()),
        }
        executed_at = str(item.get("executed_at") or "").strip()
        if executed_at:
            normalized["executed_at"] = executed_at
        if normalized_sales is not None:
            normalized["sales"] = normalized_sales
        normalized.update(self._risk_evaluation_engine.evaluate(normalized))
        return normalized

    def _find(self, action_id: str) -> StrategyAction | None:
        for item in self._items:
            if item.get("id") == action_id:
                return item
        return None

    def add(self, *, action_type: str, target_id: str, reasoning: str, status: str = "pending_confirmation", sales: int | None = None) -> StrategyAction:
        item = self._normalize_item(
            {
                "id": self._next_id(),
                "type": action_type,
                "target_id": target_id,
                "reasoning": reasoning,
                "status": status,
                "created_at": self._now(),
                "sales": sales,
            }
        )
        self._items.append(item)
        self._save()
        return deepcopy(item)

    def list(self, status: str | None = None) -> List[StrategyAction]:
        items = list(reversed(self._items))
        if status is not None:
            items = [item for item in items if item.get("status") == status]
        return deepcopy(items)

    def get(self, action_id: str) -> StrategyAction | None:
        item = self._find(action_id)
        if item is None:
            return None
        return deepcopy(item)

    def find_pending(self, *, action_type: str, target_id: str, reasoning: str) -> StrategyAction | None:
        for item in reversed(self._items):
            if (
                item.get("type") == action_type
                and item.get("target_id") == target_id
                and item.get("reasoning") == reasoning
                and item.get("status") == "pending_confirmation"
            ):
                return deepcopy(item)
        return None

    def set_status(self, action_id: str, status: str) -> StrategyAction:
        target_status = str(status).strip()
        if target_status not in self._ALLOWED_STATUSES:
            raise ValueError(f"invalid status: {status}")

        item = self._find(action_id)
        if item is None:
            raise ValueError(f"strategy action not found: {action_id}")

        item["status"] = target_status
        if target_status in {"executed", "auto_executed"}:
            item["executed_at"] = self._now()
        self._save()
        return deepcopy(item)
