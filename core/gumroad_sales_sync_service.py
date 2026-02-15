from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.integrations.gumroad_client import GumroadAPIError, GumroadClient
from core.product_launch_store import ProductLaunchStore


class GumroadSalesSyncService:
    """Synchronize Gumroad sales into ProductLaunchStore metrics."""

    def __init__(self, launch_store: ProductLaunchStore, gumroad_client: GumroadClient) -> None:
        self._launch_store = launch_store
        self._gumroad_client = gumroad_client

    def _parse_amount(self, sale: dict[str, Any]) -> float:
        raw_amount = sale.get("price")
        if raw_amount is None:
            raw_amount = sale.get("amount_cents")
        if raw_amount is None:
            return 0.0

        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            return 0.0

        if amount > 1000:
            amount = amount / 100.0
        return amount

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def sync(self, since: str | None = None) -> dict[str, Any]:
        if not self._gumroad_client.has_credentials():
            raise ValueError("Missing Gumroad credentials. Set GUMROAD_APP_ID and GUMROAD_APP_SECRET.")

        since_dt = self._parse_timestamp(since)
        launches = self._launch_store.list()
        synced_launches = 0
        new_sales_count = 0
        new_revenue = 0.0

        for launch in launches:
            launch_id = str(launch.get("id", "")).strip()
            product_id = str(launch.get("gumroad_product_id") or "").strip()
            if not launch_id or not product_id:
                continue

            last_sale_id = str(launch.get("last_gumroad_sale_id") or "").strip() or None

            try:
                payload = self._gumroad_client.get_sales_for_product(product_id=product_id, limit=200)
            except GumroadAPIError:
                raise

            sales = payload.get("sales", [])
            if not isinstance(sales, list):
                raise GumroadAPIError("Gumroad API returned invalid sales payload.")

            pending_sales: list[dict[str, Any]] = []
            for sale in sales:
                if not isinstance(sale, dict):
                    continue
                sale_id = str(sale.get("id") or "").strip()
                if last_sale_id and sale_id == last_sale_id:
                    break
                pending_sales.append(sale)

            if since_dt is not None:
                filtered_sales: list[dict[str, Any]] = []
                for sale in pending_sales:
                    sale_dt = self._parse_timestamp(sale.get("created_at"))
                    if sale_dt is not None and sale_dt <= since_dt:
                        continue
                    filtered_sales.append(sale)
                pending_sales = filtered_sales

            sale_count = len(pending_sales)
            revenue_delta = round(sum(self._parse_amount(s) for s in pending_sales), 2)

            if sale_count > 0:
                self._launch_store.add_sales_batch(launch_id, sale_count, revenue_delta)
                newest_sale_id = str(pending_sales[0].get("id") or "").strip() or last_sale_id
            else:
                newest_sale_id = last_sale_id

            self._launch_store.update_gumroad_sync_state(
                launch_id,
                last_sync_at=datetime.now(timezone.utc).isoformat(),
                last_sale_id=newest_sale_id,
            )

            synced_launches += 1
            new_sales_count += sale_count
            new_revenue = round(new_revenue + revenue_delta, 2)

        print(f"[GUMROAD] synced launches={synced_launches} new_sales={new_sales_count} revenue={new_revenue}")
        return {
            "synced_launches": synced_launches,
            "new_sales": new_sales_count,
            "revenue": new_revenue,
        }
