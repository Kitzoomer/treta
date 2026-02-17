import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.daily_loop import DailyLoopEngine
from core.ipc_http import start_http_server
from core.opportunity_store import OpportunityStore
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.strategy_action_store import StrategyActionStore


class DailyLoopEngineTest(unittest.TestCase):
    def _stores(self, root: Path):
        opportunities = OpportunityStore(path=root / "opportunities.json")
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
        strategy_actions = StrategyActionStore(path=root / "strategy_actions.json")
        return opportunities, proposals, launches, strategy_actions

    def test_phase_priority_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            opportunities, proposals, launches, strategy_actions = self._stores(root)
            engine = DailyLoopEngine(opportunities, proposals, launches, strategy_actions)

            self.assertEqual(engine.compute_phase(), "IDLE")

            opportunities.add(
                source="test",
                title="Opportunity",
                summary="New signal",
                opportunity={"score": 0.5},
                item_id="opp-1",
            )
            self.assertEqual(engine.compute_phase(), "SCAN")

            proposals.add({"id": "proposal-1", "product_name": "Demo", "status": "approved"})
            self.assertEqual(engine.compute_phase(), "BUILD")

            proposals.add({"id": "proposal-2", "product_name": "Demo", "status": "draft"})
            self.assertEqual(engine.compute_phase(), "DECIDE")

            strategy_actions.add(action_type="review", target_id="proposal-2", reasoning="Need approval")
            self.assertEqual(engine.compute_phase(), "EXECUTE")

    def test_endpoint_returns_daily_loop_status(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            opportunities, proposals, launches, strategy_actions = self._stores(root)
            strategy_actions.add(action_type="review", target_id="proposal-9", reasoning="Validate")
            engine = DailyLoopEngine(opportunities, proposals, launches, strategy_actions)

            server = start_http_server(host="127.0.0.1", port=0, daily_loop_engine=engine)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/daily_loop/status", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(payload["phase"], "EXECUTE")
                self.assertEqual(payload["route"], "#/strategy")
                self.assertIn("next_action_label", payload)
                self.assertIn("summary", payload)
                self.assertIn("timestamp", payload)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
