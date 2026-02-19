import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.services.gumroad_sync_service import GumroadSyncService
from core.revenue_attribution.store import RevenueAttributionStore


class GumroadSalesSyncServiceTest(unittest.TestCase):
    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def test_sync_updates_metrics_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Launch Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.link_gumroad_product(launch["id"], "gumroad-product-1")

            gumroad_client = Mock()
            gumroad_client.get_sales.return_value = [
                {"sale_id": "sale-2", "amount": 19.99, "created_at": "2026-01-02T00:00:00Z"},
                {"sale_id": "sale-1", "amount": 10.00, "created_at": "2026-01-01T00:00:00Z"},
            ]

            service = GumroadSyncService(launches, gumroad_client)
            summary = service.sync_sales()

            updated = launches.get(launch["id"])
            self.assertEqual(summary["synced_launches"], 1)
            self.assertEqual(summary["new_sales"], 2)
            self.assertEqual(summary["revenue_added"], 29.99)
            self.assertEqual(updated["metrics"]["sales"], 2)
            self.assertEqual(updated["metrics"]["revenue"], 29.99)
            self.assertEqual(updated["last_gumroad_sale_id"], "sale-2")
            self.assertIsNotNone(updated["last_gumroad_sync_at"])


    def test_gumroad_sync_links_sale_when_tracking_present(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-3", "product_name": "Track Kit"})
            launch = launches.add_from_proposal("proposal-3")
            launches.link_gumroad_product(launch["id"], "gumroad-product-3")

            revenue_store = RevenueAttributionStore(path=root / "revenue_attribution.json")
            revenue_store.upsert_tracking("treta-abc123-1700000000", "proposal-3", subreddit="r/saas", price=29)

            gumroad_client = Mock()
            gumroad_client.get_sales.return_value = [
                {
                    "sale_id": "sale-3",
                    "amount": 29.0,
                    "description": "Customer bought product. Tracking: treta-abc123-1700000000",
                }
            ]

            service = GumroadSyncService(launches, gumroad_client, revenue_store)
            summary = service.sync_sales()

            attributed = revenue_store.get_by_tracking("treta-abc123-1700000000")
            self.assertEqual(summary["new_sales"], 1)
            self.assertIsNotNone(attributed)
            self.assertEqual(attributed["sales"], 1)
            self.assertEqual(attributed["revenue"], 29.0)

    def test_cursor_prevents_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-2", "product_name": "Cursor Kit"})
            launch = launches.add_from_proposal("proposal-2")
            launches.link_gumroad_product(launch["id"], "gumroad-product-2")

            gumroad_client = Mock()
            gumroad_client.get_sales.return_value = [
                {"sale_id": "sale-2", "amount": 20.0, "created_at": "2026-01-02T00:00:00Z"},
                {"sale_id": "sale-1", "amount": 10.0, "created_at": "2026-01-01T00:00:00Z"},
            ]

            service = GumroadSyncService(launches, gumroad_client)
            service.sync_sales()
            second = service.sync_sales()

            updated = launches.get(launch["id"])
            self.assertEqual(second["new_sales"], 0)
            self.assertEqual(second["revenue_added"], 0.0)
            self.assertEqual(updated["metrics"]["sales"], 2)
            self.assertEqual(updated["metrics"]["revenue"], 30.0)


if __name__ == "__main__":
    unittest.main()
