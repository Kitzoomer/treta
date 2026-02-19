from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from core.integrations.gumroad_client import GumroadClient
from core.product_launch_store import ProductLaunchStore
from core.revenue_attribution.store import RevenueAttributionStore
from core.subreddit_performance_store import SubredditPerformanceStore


_TRACKING_PATTERN = re.compile(r"treta-[a-z0-9]{6}-\d+")


def extract_tracking_id(value: Any) -> str | None:
    if isinstance(value, str):
        match = _TRACKING_PATTERN.search(value.lower())
        return match.group(0) if match else None

    if isinstance(value, dict):
        for candidate in value.values():
            found = extract_tracking_id(candidate)
            if found:
                return found
        return None

    if isinstance(value, list):
        for candidate in value:
            found = extract_tracking_id(candidate)
            if found:
                return found
        return None

    return None


class GumroadSyncService:
    def __init__(
        self,
        launch_store: ProductLaunchStore,
        gumroad_client: GumroadClient,
        revenue_attribution_store: RevenueAttributionStore | None = None,
        subreddit_performance_store: SubredditPerformanceStore | None = None,
    ) -> None:
        self._launch_store = launch_store
        self._gumroad_client = gumroad_client
        self._revenue_attribution_store = revenue_attribution_store
        self._subreddit_performance_store = subreddit_performance_store

    def sync_sales(self) -> dict[str, float | int]:
        synced_launches = 0
        total_new_sales = 0
        total_revenue_added = 0.0

        for launch in self._launch_store.list():
            launch_id = str(launch.get("id") or "").strip()
            gumroad_product_id = str(launch.get("gumroad_product_id") or "").strip()
            if not launch_id or not gumroad_product_id:
                continue

            synced_launches += 1
            last_sale_id = str(launch.get("last_gumroad_sale_id") or "").strip() or None

            sales = self._gumroad_client.get_sales(gumroad_product_id)

            new_sales: list[dict[str, object]] = []
            for sale in sales:
                sale_id = str(sale.get("sale_id") or "").strip()
                if not sale_id:
                    continue
                if last_sale_id and sale_id == last_sale_id:
                    break
                new_sales.append(sale)

            if new_sales:
                revenue_added = round(sum(float(sale.get("amount", 0.0)) for sale in new_sales), 2)
                self._launch_store.add_sales_batch(launch_id, len(new_sales), revenue_added)
                newest_sale_id = str(new_sales[0]["sale_id"])

                if self._revenue_attribution_store is not None:
                    for sale in new_sales:
                        tracking_id = extract_tracking_id(sale)
                        if not tracking_id:
                            continue
                        attributed = self._revenue_attribution_store.record_sale(
                            tracking_id,
                            sale_count=1,
                            revenue_delta=float(sale.get("amount", 0.0) or 0.0),
                        )
                        if (
                            attributed is not None
                            and self._subreddit_performance_store is not None
                            and str(attributed.get("subreddit") or "").strip()
                        ):
                            self._subreddit_performance_store.record_sale(
                                str(attributed.get("subreddit") or "").strip(),
                                float(sale.get("amount", 0.0) or 0.0),
                            )
            else:
                revenue_added = 0.0
                newest_sale_id = last_sale_id

            self._launch_store.update_gumroad_sync_state(
                launch_id,
                last_sync_at=datetime.now(timezone.utc).isoformat(),
                last_sale_id=newest_sale_id,
            )

            total_new_sales += len(new_sales)
            total_revenue_added = round(total_revenue_added + revenue_added, 2)

        print(f"[GUMROAD] synced={synced_launches} sales={total_new_sales} revenue={total_revenue_added}")
        return {
            "synced_launches": synced_launches,
            "new_sales": total_new_sales,
            "revenue_added": total_revenue_added,
        }
