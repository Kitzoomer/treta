import tempfile
import unittest
from pathlib import Path

from core.product_plan_store import ProductPlanStore


class ProductPlanStoreTest(unittest.TestCase):
    def test_persistence_works_across_restarts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            path = root / "product_plans.json"

            store = ProductPlanStore(path=path)
            created = store.add(
                {
                    "plan_id": "plan-1",
                    "proposal_id": "proposal-1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "product_name": "Planner Kit",
                }
            )

            reloaded = ProductPlanStore(path=path)
            loaded = reloaded.get("plan-1")

            self.assertEqual(loaded, created)
            self.assertEqual(reloaded.get_by_proposal_id("proposal-1"), created)

    def test_missing_or_malformed_file_falls_back_to_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            path = root / "product_plans.json"

            missing_store = ProductPlanStore(path=path)
            self.assertEqual(missing_store.list(), [])
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "[]")

            path.write_text("{bad json", encoding="utf-8")
            malformed_store = ProductPlanStore(path=path)
            self.assertEqual(malformed_store.list(), [])


if __name__ == "__main__":
    unittest.main()
