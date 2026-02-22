import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.strategy_engine import StrategyEngine


class StrategyEngineTest(unittest.TestCase):
    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def _seed_launches(self, proposals: ProductProposalStore, launches: ProductLaunchStore):
        proposals.add({"id": "proposal-1", "product_name": "Creator Growth Kit"})
        proposals.add({"id": "proposal-2", "product_name": "Creator Growth Course"})
        proposals.add({"id": "proposal-3", "product_name": "Automation Template"})

        launch_1 = launches.add_from_proposal("proposal-1")
        launch_2 = launches.add_from_proposal("proposal-2")
        launch_3 = launches.add_from_proposal("proposal-3")

        launches.add_sale(launch_1["id"], 25)
        launches.add_sale(launch_1["id"], 25)
        launches.add_sale(launch_1["id"], 25)
        launches.add_sale(launch_1["id"], 25)
        launches.add_sale(launch_1["id"], 25)

        launches.add_sale(launch_2["id"], 20)

        return launch_1["id"], launch_2["id"], launch_3["id"]

    def test_generate_recommendations_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            scale_id, test_price_id, fix_id = self._seed_launches(proposals, launches)

            stale_created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
            active_created_at = datetime(2025, 1, 9, tzinfo=timezone.utc).isoformat()

            raw_launches = json.loads((root / "product_launches.json").read_text(encoding="utf-8"))
            for launch in raw_launches:
                if launch["id"] == fix_id:
                    launch["created_at"] = stale_created_at
                else:
                    launch["created_at"] = active_created_at
            (root / "product_launches.json").write_text(json.dumps(raw_launches), encoding="utf-8")

            launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
            engine = StrategyEngine(product_launch_store=launches)
            engine._utcnow = lambda: datetime(2025, 1, 11, tzinfo=timezone.utc)

            payload = engine.generate_recommendations()

            self.assertEqual(payload["global_summary"]["total_revenue"], 145.0)
            self.assertEqual(payload["global_summary"]["total_sales"], 6)
            self.assertEqual(payload["global_summary"]["revenue_by_category"], {"course": 20.0, "kit": 125.0, "template": 0.0})
            self.assertEqual(
                payload["global_summary"]["days_since_launch"],
                {fix_id: 10, scale_id: 2, test_price_id: 2},
            )
            self.assertEqual(
                sorted(payload["product_actions"], key=lambda item: item["action"]),
                [
                    {
                        "product_id": fix_id,
                        "action": "FIX_OR_ARCHIVE",
                        "reason": "No sales after 10 days since launch.",
                        "confidence": 88,
                    },
                    {
                        "product_id": scale_id,
                        "action": "SCALE_PRODUCT",
                        "reason": "5 sales and $125.00 revenue meet scale thresholds.",
                        "confidence": 92,
                    },
                    {
                        "product_id": test_price_id,
                        "action": "TEST_PRICE",
                        "reason": "1 sales but only $20.00 revenue indicates price optimization opportunity.",
                        "confidence": 84,
                    },
                ],
            )
            self.assertEqual(
                payload["category_actions"],
                [
                    {
                        "category": "kit",
                        "action": "CATEGORY_EXPANSION",
                        "reason": "Category contributes 86% of total revenue ($125.00/$145.00).",
                        "confidence": 90,
                    }
                ],
            )

    def test_strategy_recommendations_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            self._seed_launches(proposals, launches)

            engine = StrategyEngine(product_launch_store=launches)
            server = start_http_server(host="127.0.0.1", port=0, strategy_engine=engine)
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/strategy/recommendations", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertTrue(payload["ok"])
            self.assertIn("global_summary", payload["data"])
            self.assertIn("product_actions", payload["data"])
            self.assertIn("category_actions", payload["data"])


if __name__ == "__main__":
    unittest.main()
