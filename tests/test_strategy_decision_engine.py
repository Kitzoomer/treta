import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.strategy_decision_engine import StrategyDecisionEngine


class StrategyDecisionEngineTest(unittest.TestCase):
    def _stores(self, root: Path):
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        return proposals, launches

    def test_rule_scale_when_sales_at_least_five(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")

            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            decision = StrategyDecisionEngine(product_launch_store=launches).decide()

            self.assertIn(
                {
                    "type": "scale",
                    "target_id": launch["id"],
                    "reasoning": "Launch has 5 sales, which meets the scale threshold.",
                },
                decision["actions"],
            )

    def test_rule_review_when_zero_sales_after_seven_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")

            items = json.loads((root / "product_launches.json").read_text(encoding="utf-8"))
            items[0]["created_at"] = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
            (root / "product_launches.json").write_text(json.dumps(items), encoding="utf-8")

            launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
            engine = StrategyDecisionEngine(product_launch_store=launches)
            engine._utcnow = lambda: datetime(2025, 1, 10, tzinfo=timezone.utc)

            decision = engine.decide()

            self.assertIn(
                {
                    "type": "review",
                    "target_id": launch["id"],
                    "reasoning": "Launch has 0 sales after 9 days.",
                },
                decision["actions"],
            )

    def test_rule_price_test_when_high_revenue_per_sale_and_low_sales(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            launches.add_sale(launch["id"], 100)

            decision = StrategyDecisionEngine(product_launch_store=launches).decide()

            self.assertIn(
                {
                    "type": "price_test",
                    "target_id": launch["id"],
                    "reasoning": "Revenue per sale is 100.00 with only 1 total sales.",
                },
                decision["actions"],
            )

    def test_rule_new_product_when_no_active_launches(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)

            decision = StrategyDecisionEngine(product_launch_store=launches).decide()

            self.assertIn(
                {
                    "type": "new_product",
                    "target_id": "portfolio",
                    "reasoning": "No active launches were found.",
                },
                decision["actions"],
            )

    def test_strategy_decide_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals, launches = self._stores(root)
            proposals.add({"id": "proposal-1", "product_name": "Growth Kit"})
            launch = launches.add_from_proposal("proposal-1")
            launches.transition_status(launch["id"], "active")
            for _ in range(5):
                launches.add_sale(launch["id"], 10)

            engine = StrategyDecisionEngine(product_launch_store=launches)
            server = start_http_server(host="127.0.0.1", port=0, strategy_decision_engine=engine)
            try:
                port = server.server_port
                with urlopen(f"http://127.0.0.1:{port}/strategy/decide", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertIn("actions", payload)
            self.assertGreaterEqual(payload["confidence"], 0)
            self.assertLessEqual(payload["confidence"], 10)


if __name__ == "__main__":
    unittest.main()
