import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.gumroad_sales_sync_service import GumroadSalesSyncService
from core.integrations.gumroad_client import GumroadAPIError
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore


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
            gumroad_client.has_credentials.return_value = True
            gumroad_client.get_sales_for_product.return_value = {
                "sales": [
                    {"id": "sale-2", "price": "19.99"},
                    {"id": "sale-1", "price": "10.00"},
                ]
            }

            service = GumroadSalesSyncService(launches, gumroad_client)
            summary = service.sync()

            updated = launches.get(launch["id"])
            self.assertEqual(summary["synced_launches"], 1)
            self.assertEqual(summary["new_sales"], 2)
            self.assertEqual(summary["revenue"], 29.99)
            self.assertEqual(updated["metrics"]["sales"], 2)
            self.assertEqual(updated["metrics"]["revenue"], 29.99)
            self.assertEqual(updated["last_gumroad_sale_id"], "sale-2")
            self.assertIsNotNone(updated["last_gumroad_sync_at"])

            reloaded_proposals = ProductProposalStore(path=root / "product_proposals.json")
            reloaded_launches = ProductLaunchStore(
                proposal_store=reloaded_proposals,
                path=root / "product_launches.json",
            )
            persisted = reloaded_launches.get(launch["id"])
            self.assertEqual(persisted["metrics"]["sales"], 2)
            self.assertEqual(persisted["metrics"]["revenue"], 29.99)
            self.assertEqual(persisted["last_gumroad_sale_id"], "sale-2")

    def test_cursor_prevents_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-2", "product_name": "Cursor Kit"})
            launch = launches.add_from_proposal("proposal-2")
            launches.link_gumroad_product(launch["id"], "gumroad-product-2")

            gumroad_client = Mock()
            gumroad_client.has_credentials.return_value = True
            gumroad_client.get_sales_for_product.return_value = {
                "sales": [
                    {"id": "sale-2", "price": "20.00"},
                    {"id": "sale-1", "price": "10.00"},
                ]
            }

            service = GumroadSalesSyncService(launches, gumroad_client)
            service.sync()
            second = service.sync()

            updated = launches.get(launch["id"])
            self.assertEqual(second["new_sales"], 0)
            self.assertEqual(second["revenue"], 0.0)
            self.assertEqual(updated["metrics"]["sales"], 2)
            self.assertEqual(updated["metrics"]["revenue"], 30.0)

    def test_missing_credentials_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-3", "product_name": "No Token Kit"})
            launch = launches.add_from_proposal("proposal-3")
            launches.link_gumroad_product(launch["id"], "gumroad-product-3")

            gumroad_client = Mock()
            gumroad_client.has_credentials.return_value = False

            service = GumroadSalesSyncService(launches, gumroad_client)
            with self.assertRaisesRegex(ValueError, "Missing Gumroad credentials"):
                service.sync()

    def test_api_failure_raises_gumroad_api_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-4", "product_name": "Failure Kit"})
            launch = launches.add_from_proposal("proposal-4")
            launches.link_gumroad_product(launch["id"], "gumroad-product-4")

            gumroad_client = Mock()
            gumroad_client.has_credentials.return_value = True
            gumroad_client.get_sales_for_product.side_effect = GumroadAPIError("bad gateway")

            service = GumroadSalesSyncService(launches, gumroad_client)
            with self.assertRaisesRegex(GumroadAPIError, "bad gateway"):
                service.sync()


if __name__ == "__main__":
    unittest.main()
