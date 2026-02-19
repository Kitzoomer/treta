import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from core.bus import EventBus
from core.control import Control
from core.ipc_http import start_http_server
from core.opportunity_store import OpportunityStore
from core.product_launch_store import ProductLaunchStore
from core.product_plan_store import ProductPlanStore
from core.product_proposal_store import ProductProposalStore
from core.reddit_public.config import update_config
from core.subreddit_performance_store import SubredditPerformanceStore


class DominantChannelLockTest(unittest.TestCase):
    def _build_control(self, root: Path, bus: EventBus | None = None) -> Control:
        proposal_store = ProductProposalStore(path=root / "product_proposals.json")
        control = Control(
            opportunity_store=OpportunityStore(path=root / "opportunities.json"),
            product_proposal_store=proposal_store,
            product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
            product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
            subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
            bus=bus,
        )
        control._reddit_posts_path = lambda: root / "reddit_posts.json"
        return control

    def test_top_subreddit_selection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            control = self._build_control(root)

            for _ in range(5):
                control.subreddit_performance_store.record_post_attempt("alpha")
            control.subreddit_performance_store.record_sale("alpha", 50.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("beta")
            control.subreddit_performance_store.record_sale("beta", 36.0)

            for _ in range(4):
                control.subreddit_performance_store.record_post_attempt("gamma")
            control.subreddit_performance_store.record_sale("gamma", 8.0)

            self.assertEqual(control._get_top_subreddits_by_roi(limit=2), ["beta", "alpha"])

    def test_scan_restricted_to_top_two(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bus = EventBus()
            control = self._build_control(root, bus=bus)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("alpha")
            control.subreddit_performance_store.record_sale("alpha", 30.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("beta")
            control.subreddit_performance_store.record_sale("beta", 24.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("gamma")
            control.subreddit_performance_store.record_sale("gamma", 9.0)

            update_config({"subreddits": ["alpha", "beta", "gamma"], "pain_threshold": 60, "source": "reddit_public"})

            captured_subreddits = []

            def _scan_stub(subreddits):
                captured_subreddits.extend(subreddits)
                return []

            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", side_effect=_scan_stub):
                result = control.run_reddit_public_scan()

            self.assertEqual(captured_subreddits, ["alpha", "beta"])
            self.assertEqual(result["diagnostics"]["dominant_subreddits"], ["alpha", "beta"])

    def test_execution_skips_non_dominant(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bus = EventBus()
            control = self._build_control(root, bus=bus)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("alpha")
            control.subreddit_performance_store.record_sale("alpha", 30.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("beta")
            control.subreddit_performance_store.record_sale("beta", 24.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("gamma")
            control.subreddit_performance_store.record_sale("gamma", 9.0)

            posts = [
                {
                    "id": "gamma-1",
                    "title": "pricing help",
                    "selftext": "need urgent help",
                    "score": 70,
                    "num_comments": 20,
                    "subreddit": "gamma",
                    "url": "https://reddit.test/gamma-1",
                }
            ]

            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.control.get_config",
                return_value={"subreddits": ["gamma"], "pain_threshold": 60, "source": "reddit_public"},
            ), patch(
                "core.control.compute_pain_score",
                return_value={"pain_score": 90, "intent_type": "purchase_ready", "urgency_level": "high"},
            ):
                result = control.run_reddit_public_scan()

            detected = []
            while True:
                event = bus.pop(timeout=0.001)
                if event is None:
                    break
                if event.type == "OpportunityDetected":
                    detected.append(event)

            self.assertEqual(len(detected), 0)
            self.assertEqual(result["diagnostics"]["skipped_due_to_channel_lock"], ["gamma"])

    def test_dominant_endpoint_shape(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            bus = EventBus()
            control = self._build_control(root, bus=bus)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("alpha")
            control.subreddit_performance_store.record_sale("alpha", 30.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("beta")
            control.subreddit_performance_store.record_sale("beta", 24.0)

            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("gamma")
            control.subreddit_performance_store.record_sale("gamma", 9.0)

            server = start_http_server(host="127.0.0.1", port=0, bus=bus, control=control)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/revenue/dominant", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(payload["ok"])
                self.assertEqual(payload["data"]["dominant_subreddits"], ["alpha", "beta"])
                self.assertEqual(payload["data"]["total_tracked"], 3)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
