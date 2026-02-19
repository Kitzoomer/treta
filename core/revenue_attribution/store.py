from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any

from core.persistence.json_io import atomic_read_json, atomic_write_json, quarantine_corrupt_file


class RevenueAttributionStore:
    _DEFAULT_DATA_DIR = "./.treta_data"
    _DEFAULT_REDDIT_WINDOW_HOURS = 24

    def __init__(self, path: Path | None = None, reddit_attribution_window_hours: int | None = None) -> None:
        data_dir = Path(os.getenv("TRETA_DATA_DIR", self._DEFAULT_DATA_DIR))
        self._path = path or data_dir / "revenue_attribution.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        configured_window = reddit_attribution_window_hours
        if configured_window is None:
            configured_window = int(os.getenv("TRETA_REDDIT_ATTRIBUTION_WINDOW_HOURS", self._DEFAULT_REDDIT_WINDOW_HOURS))
        self._reddit_attribution_window = max(1, int(configured_window))
        self._items, self._sales = self._load_state()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_timestamp(self, value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def _load_state(self) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        if not self._path.exists():
            return {}, []

        loaded = atomic_read_json(self._path, {"trackings": [], "sales": []})

        if isinstance(loaded, list):
            tracking_rows = loaded
            sales_rows: list[dict[str, Any]] = []
        elif isinstance(loaded, dict):
            tracking_rows = loaded.get("trackings", [])
            sales_rows = loaded.get("sales", [])
        else:
            quarantine_corrupt_file(self._path, ValueError("expected list or dict"))
            return {}, []

        items: dict[str, dict[str, Any]] = {}
        if isinstance(tracking_rows, list):
            for row in tracking_rows:
                if not isinstance(row, dict):
                    continue
                tracking_id = str(row.get("tracking_id") or "").strip()
                proposal_id = str(row.get("proposal_id") or "").strip()
                if not tracking_id or not proposal_id:
                    continue
                normalized = {
                    "tracking_id": tracking_id,
                    "proposal_id": proposal_id,
                    "product_id": str(row.get("product_id") or proposal_id).strip() or proposal_id,
                    "subreddit": row.get("subreddit"),
                    "post_id": row.get("post_id"),
                    "price": row.get("price"),
                    "created_at": str(row.get("created_at") or self._now()),
                }
                items[tracking_id] = normalized

        sales: list[dict[str, Any]] = []
        if isinstance(sales_rows, list):
            for row in sales_rows:
                if not isinstance(row, dict):
                    continue
                sale_id = str(row.get("sale_id") or "").strip()
                product_id = str(row.get("product_id") or "").strip()
                if not sale_id or not product_id:
                    continue
                attribution = row.get("attribution", {}) if isinstance(row.get("attribution"), dict) else {}
                sales.append(
                    {
                        "sale_id": sale_id,
                        "product_id": product_id,
                        "revenue": round(float(row.get("revenue", 0.0) or 0.0), 2),
                        "timestamp": str(row.get("timestamp") or self._now()),
                        "attribution": {
                            "channel": str(attribution.get("channel") or "unknown"),
                            "subreddit": attribution.get("subreddit"),
                            "post_id": attribution.get("post_id"),
                        },
                    }
                )

        return items, sales

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._path, {"trackings": list(self._items.values()), "sales": self._sales})

    def upsert_tracking(
        self,
        tracking_id: str,
        proposal_id: str,
        subreddit: str | None = None,
        price: float | int | None = None,
        created_at: str | None = None,
        post_id: str | None = None,
        product_id: str | None = None,
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
            "product_id": str(product_id or existing.get("product_id") or normalized_proposal).strip() or normalized_proposal,
            "subreddit": subreddit if subreddit is not None else existing.get("subreddit"),
            "post_id": post_id if post_id is not None else existing.get("post_id"),
            "price": price if price is not None else existing.get("price"),
            "created_at": str(created_at or existing.get("created_at") or self._now()),
        }
        if extra:
            record.update(extra)

        self._items[normalized_tracking] = record
        self._save()
        return deepcopy(record)

    def _infer_channel(self, sold_at: str, tracking: dict[str, Any] | None) -> str:
        if tracking is None:
            return "unknown"
        created_at = self._parse_timestamp(tracking.get("created_at"))
        sold_at_dt = self._parse_timestamp(sold_at)
        if created_at is None or sold_at_dt is None:
            return "unknown"
        if sold_at_dt < created_at:
            return "unknown"
        if sold_at_dt <= created_at + timedelta(hours=self._reddit_attribution_window):
            return "reddit"
        return "unknown"

    def record_sale(
        self,
        tracking_id: str,
        sale_count: int = 1,
        revenue_delta: float = 0.0,
        sale_id: str | None = None,
        sold_at: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_tracking = str(tracking_id).strip()
        current = self._items.get(normalized_tracking) if normalized_tracking else None
        if current is None:
            return None

        count = max(1, int(sale_count or 1))
        per_sale_revenue = float(revenue_delta) / float(count)
        timestamp = str(sold_at or self._now())
        product_id = str(current.get("product_id") or current.get("proposal_id") or "").strip()
        channel = self._infer_channel(timestamp, current)

        for index in range(count):
            resolved_sale_id = str(sale_id or f"{normalized_tracking}-sale-{len(self._sales) + 1 + index}")
            self._sales.append(
                {
                    "sale_id": resolved_sale_id,
                    "product_id": product_id,
                    "revenue": round(per_sale_revenue, 2),
                    "timestamp": timestamp,
                    "attribution": {
                        "channel": channel,
                        "subreddit": current.get("subreddit") if channel == "reddit" else None,
                        "post_id": current.get("post_id") if channel == "reddit" else None,
                    },
                }
            )

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
        by_product: dict[str, dict[str, float | int]] = {}
        by_channel: dict[str, dict[str, float | int]] = {}
        by_subreddit: dict[str, dict[str, float | int]] = {}

        for sale in self._sales:
            product_id = str(sale.get("product_id") or "").strip()
            revenue = float(sale.get("revenue", 0.0) or 0.0)
            attribution = sale.get("attribution", {}) if isinstance(sale.get("attribution"), dict) else {}
            channel = str(attribution.get("channel") or "unknown")
            subreddit = str(attribution.get("subreddit") or "").strip()

            totals["sales"] += 1
            totals["revenue"] = round(float(totals["revenue"]) + revenue, 2)

            if product_id:
                bucket = by_product.setdefault(product_id, {"sales": 0, "revenue": 0.0})
                bucket["sales"] = int(bucket["sales"]) + 1
                bucket["revenue"] = round(float(bucket["revenue"]) + revenue, 2)

            channel_bucket = by_channel.setdefault(channel, {"sales": 0, "revenue": 0.0})
            channel_bucket["sales"] = int(channel_bucket["sales"]) + 1
            channel_bucket["revenue"] = round(float(channel_bucket["revenue"]) + revenue, 2)

            if subreddit:
                sub_bucket = by_subreddit.setdefault(subreddit, {"sales": 0, "revenue": 0.0, "views": 0, "conversion_rate": 0.0})
                sub_bucket["sales"] = int(sub_bucket["sales"]) + 1
                sub_bucket["revenue"] = round(float(sub_bucket["revenue"]) + revenue, 2)

        for subreddit, bucket in by_subreddit.items():
            tracking_views = sum(
                1
                for row in self._items.values()
                if str(row.get("subreddit") or "").strip() == subreddit
            )
            bucket["views"] = tracking_views
            bucket["conversion_rate"] = round(int(bucket["sales"]) / tracking_views, 4) if tracking_views > 0 else 0.0

        return {
            "totals": totals,
            "by_product": by_product,
            "by_channel": by_channel,
            "by_subreddit": by_subreddit,
            "sales": deepcopy(self._sales),
            # Backward-compatible alias.
            "by_proposal": by_product,
        }
