from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from core.persistence.json_io import atomic_read_json, atomic_write_json, quarantine_corrupt_file


class RevenueAttributionStore:
    _DEFAULT_DATA_DIR = "./.treta_data"

    def __init__(self, path: Path | None = None) -> None:
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "revenue_attribution.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, dict[str, Any]] = self._load_items()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_items(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}

        loaded = atomic_read_json(self._path, [])
        if not isinstance(loaded, list):
            quarantine_corrupt_file(self._path, ValueError("expected list"))
            return {}

        items: dict[str, dict[str, Any]] = {}
        for row in loaded:
            if not isinstance(row, dict):
                continue
            tracking_id = str(row.get("tracking_id") or "").strip()
            proposal_id = str(row.get("proposal_id") or "").strip()
            if not tracking_id or not proposal_id:
                continue
            normalized = {
                "tracking_id": tracking_id,
                "proposal_id": proposal_id,
                "subreddit": row.get("subreddit"),
                "price": row.get("price"),
                "created_at": str(row.get("created_at") or self._now()),
                "sales": int(row.get("sales", 0) or 0),
                "revenue": float(row.get("revenue", 0.0) or 0.0),
            }
            for key, value in row.items():
                if key not in normalized:
                    normalized[key] = value
            items[tracking_id] = normalized
        return items

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, list(self._items.values()))

    def upsert_tracking(
        self,
        tracking_id: str,
        proposal_id: str,
        subreddit: str | None = None,
        price: float | int | None = None,
        created_at: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_tracking = str(tracking_id).strip()
        normalized_proposal = str(proposal_id).strip()
        if not normalized_tracking:
            raise ValueError("tracking_id is required")
        if not normalized_proposal:
            raise ValueError("proposal_id is required")

        existing = self._items.get(normalized_tracking, {})
        record = {
            "tracking_id": normalized_tracking,
            "proposal_id": normalized_proposal,
            "subreddit": subreddit if subreddit is not None else existing.get("subreddit"),
            "price": price if price is not None else existing.get("price"),
            "created_at": str(created_at or existing.get("created_at") or self._now()),
            "sales": int(existing.get("sales", 0) or 0),
            "revenue": float(existing.get("revenue", 0.0) or 0.0),
        }
        if extra:
            record.update(extra)

        self._items[normalized_tracking] = record
        self._save()
        return deepcopy(record)

    def record_sale(self, tracking_id: str, sale_count: int = 1, revenue_delta: float = 0.0) -> dict[str, Any] | None:
        normalized_tracking = str(tracking_id).strip()
        if not normalized_tracking:
            return None

        current = self._items.get(normalized_tracking)
        if current is None:
            return None

        current["sales"] = int(current.get("sales", 0) or 0) + int(sale_count)
        current["revenue"] = round(float(current.get("revenue", 0.0) or 0.0) + float(revenue_delta), 2)
        self._save()
        return deepcopy(current)

    def list_all(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._items.values()]

    def get_by_tracking(self, tracking_id: str) -> dict[str, Any] | None:
        item = self._items.get(str(tracking_id).strip())
        if item is None:
            return None
        return deepcopy(item)

    def summary(self) -> dict[str, Any]:
        totals = {"sales": 0, "revenue": 0.0}
        by_proposal: dict[str, dict[str, float | int]] = {}
        by_subreddit: dict[str, dict[str, float | int]] = {}

        for item in self._items.values():
            proposal_id = str(item.get("proposal_id") or "").strip()
            subreddit = str(item.get("subreddit") or "").strip()
            sales = int(item.get("sales", 0) or 0)
            revenue = float(item.get("revenue", 0.0) or 0.0)

            totals["sales"] += sales
            totals["revenue"] = round(float(totals["revenue"]) + revenue, 2)

            if proposal_id:
                if proposal_id not in by_proposal:
                    by_proposal[proposal_id] = {"sales": 0, "revenue": 0.0}
                by_proposal[proposal_id]["sales"] = int(by_proposal[proposal_id]["sales"]) + sales
                by_proposal[proposal_id]["revenue"] = round(float(by_proposal[proposal_id]["revenue"]) + revenue, 2)

            if subreddit:
                if subreddit not in by_subreddit:
                    by_subreddit[subreddit] = {"sales": 0, "revenue": 0.0}
                by_subreddit[subreddit]["sales"] = int(by_subreddit[subreddit]["sales"]) + sales
                by_subreddit[subreddit]["revenue"] = round(float(by_subreddit[subreddit]["revenue"]) + revenue, 2)

        return {
            "totals": totals,
            "by_proposal": by_proposal,
            "by_subreddit": by_subreddit,
        }
