from __future__ import annotations

from collections import deque
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List


ProductPlan = Dict[str, Any]
logger = logging.getLogger(__name__)


class ProductPlanStore:
    """In-memory bounded store for product plans."""

    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, capacity: int = 50, path: Path | None = None):
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "product_plans.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: deque[ProductPlan] = deque(self._load_from_disk(), maxlen=capacity)

    def _load_from_disk(self) -> List[ProductPlan]:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._path.exists():
            try:
                self._path.write_text("[]\n", encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to initialize product plan store at %s: %s", self._path, exc)
            return []

        try:
            content = self._path.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning("Product plan store file is empty at %s; using empty store", self._path)
                return []
            loaded = json.loads(content)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load product plans from %s: %s", self._path, exc)
            return []

        if not isinstance(loaded, list):
            logger.warning("Product plan store at %s did not contain a JSON list; using empty store", self._path)
            return []
        return [dict(item) for item in loaded if isinstance(item, dict)]

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = list(self._items)

        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
            ) as temp_file:
                json.dump(payload, temp_file, indent=2)
                temp_file.write("\n")
                tmp_path = Path(temp_file.name)
            os.replace(tmp_path, self._path)
        except OSError as exc:
            logger.error("Failed to persist product plans to %s: %s", self._path, exc)
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def add(self, plan: Dict[str, Any]) -> ProductPlan:
        item = dict(plan)
        self._items.append(item)
        self._persist()
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
