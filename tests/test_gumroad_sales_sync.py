import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.services.gumroad_sync_service import GumroadSyncService


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
