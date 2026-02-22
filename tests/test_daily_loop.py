import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from core.bus import EventBus
from core.control import Control
from core.daily_loop import DailyLoopEngine
from core.events import Event
from core.reddit_intelligence.daily_plan_store import RedditDailyPlanStore
from core.ipc_http import start_http_server
from core.opportunity_store import OpportunityStore
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore
from core.reddit_public.config import DEFAULT_CONFIG, update_config
from core.strategy_action_store import StrategyActionStore


class DailyLoopEngineTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        update_config(DEFAULT_CONFIG.copy())

    def tearDown(self):
        update_config(DEFAULT_CONFIG.copy())

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


    def test_daily_loop_generates_reddit_plan(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        RedditDailyPlanStore.save({})

        signals = [
            {"id": f"signal-{index}", "subreddit": f"sub{index}", "detected_pain_type": "direct"}
            for index in range(1, 8)
        ]

        control = Control(bus=self.bus)
        with patch("core.control.Control._scan_reddit_public_opportunities", return_value=None), patch(
            "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
            return_value=signals[:5],
        ):
            control.consume(Event(type="RunInfoproductScan", payload={}, source="test"))

        plan = RedditDailyPlanStore.get_latest()
        self.assertTrue(plan)
        self.assertLessEqual(len(plan.get("signals", [])), 5)
        self.assertTrue(str(plan.get("summary", "")).strip())

        recent_events = self.bus.recent(limit=20)
        daily_events = [event for event in recent_events if event.type == "RedditDailyPlanGenerated"]
        self.assertTrue(daily_events)

    def test_infoproduct_scan_uses_openclaw_when_flagged(self):
        update_config({"source": "openclaw"})
        control = Control(bus=self.bus)

        with patch.object(control, "run_openclaw_reddit_scan", return_value={}), patch.object(
            control, "run_reddit_public_scan", return_value={}
        ) as reddit_public_scan, patch("core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions", return_value=[]):
            control.consume(Event(type="RunInfoproductScan", payload={}, source="test"))

        reddit_public_scan.assert_not_called()

    def test_infoproduct_scan_defaults_to_reddit_public(self):
        control = Control(bus=self.bus)

        with patch.object(control, "run_openclaw_reddit_scan", return_value={}) as openclaw_scan, patch.object(
            control, "run_reddit_public_scan", return_value={}
        ), patch("core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions", return_value=[]):
            control.consume(Event(type="RunInfoproductScan", payload={}, source="test"))

        openclaw_scan.assert_not_called()

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

                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["phase"], "EXECUTE")
                self.assertEqual(payload["data"]["route"], "#/strategy")
                self.assertIn("next_action_label", payload)
                self.assertIn("summary", payload)
                self.assertIn("timestamp", payload)
            finally:
                server.shutdown()
                server.server_close()

    def test_endpoint_returns_reddit_today_plan(self):
        RedditDailyPlanStore.save(
            {
                "generated_at": "2026-01-01T00:00:00",
                "signals": ["signal-1", "signal-2"],
                "summary": "Today's Reddit focus: \n1. r/freelance - direct signal",
            }
        )

        server = start_http_server(host="127.0.0.1", port=0)
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/reddit/today_plan", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["generated_at"], "2026-01-01T00:00:00")
            self.assertEqual(payload["data"]["signals"], ["signal-1", "signal-2"])
            self.assertTrue(payload["data"]["summary"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
