import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.ipc_http import start_http_server
from core.performance_engine import PerformanceEngine
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore


class PerformanceEngineTest(unittest.TestCase):
    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def _seed_launches(self, proposals: ProductProposalStore, launches: ProductLaunchStore):
        proposals.add({"id": "proposal-1", "product_name": "Media Kit + Pitch Kit"})
        proposals.add({"id": "proposal-2", "product_name": "Automation Template"})

        launch_1 = launches.add_from_proposal("proposal-1")
        launch_2 = launches.add_from_proposal("proposal-2")

        launches.add_sale(launch_1["id"], 20)
        launches.add_sale(launch_1["id"], 30)
        launches.add_sale(launch_2["id"], 10)

    def test_generate_insights_returns_expected_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            self._seed_launches(proposals, launches)

            engine = PerformanceEngine(product_launch_store=launches)

            self.assertEqual(engine.total_revenue(), 60.0)
            self.assertEqual(engine.total_sales(), 3)
            self.assertEqual(
                engine.revenue_by_product(),
                {"Media Kit + Pitch Kit": 50.0, "Automation Template": 10.0},
            )
            self.assertEqual(engine.best_performing_product(), "Media Kit + Pitch Kit")
            self.assertEqual(engine.revenue_by_product_type(), {"kit": 50.0, "template": 10.0})
            self.assertEqual(
                engine.generate_insights(),
                {
                    "total_revenue": 60.0,
                    "total_sales": 3,
                    "best_product": "Media Kit + Pitch Kit",
                    "top_category": "kit",
                    "recommendation": "Double down on creator-focused kits priced under $30.",
                },
            )

    def test_performance_summary_endpoint_returns_engine_insights(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            self._seed_launches(proposals, launches)
            engine = PerformanceEngine(product_launch_store=launches)

            server = start_http_server(host="127.0.0.1", port=0, performance_engine=engine)
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/performance/summary", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(payload["best_product"], "Media Kit + Pitch Kit")
            self.assertEqual(payload["top_category"], "kit")
            self.assertEqual(payload["total_sales"], 3)
            self.assertEqual(payload["total_revenue"], 60.0)


if __name__ == "__main__":
    unittest.main()
