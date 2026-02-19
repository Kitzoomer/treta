import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.bus import EventBus
from core.control import Control
from core.product_proposal_store import ProductProposalStore
from core.reddit_public.config import DEFAULT_CONFIG, update_config


class OpenClawScanTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bus = EventBus()
        update_config(DEFAULT_CONFIG.copy())
        update_config({"source": "openclaw"})

        self.proposal_store = ProductProposalStore(path=Path(self.temp_dir.name) / "product_proposals.json")
        self.control = Control(product_proposal_store=self.proposal_store, bus=self.bus)

        def _control_temp_reddit_posts_path():
            return Path(self.temp_dir.name) / "reddit_posts.json"

        self.original_control_reddit_path = self.control._reddit_posts_path
        self.control._reddit_posts_path = _control_temp_reddit_posts_path

    def tearDown(self):
        self.control._reddit_posts_path = self.original_control_reddit_path
        update_config(DEFAULT_CONFIG.copy())
        self.temp_dir.cleanup()

    def test_openclaw_scan_normalizes_to_existing_summary_shape(self):
        raw = {
            "posts": [
                {
                    "id": "oc_1",
                    "subreddit": "freelance",
                    "title": "Need help with pricing",
                    "pain_score": 84,
                    "intent_type": "monetization",
                    "urgency_level": "high",
                },
                {
                    "id": "oc_2",
                    "subreddit": "freelance",
                    "title": "Stuck with outreach",
                    "pain_score": 70,
                    "intent_type": "acquisition",
                    "urgency_level": "medium",
                },
            ]
        }

        with patch("core.openclaw_agent.OpenClawRedditScanner.scan", return_value=raw):
            result = self.control.run_reddit_scan()

        self.assertEqual(set(result.keys()), {"analyzed", "qualified", "by_subreddit", "posts", "timestamp"})
        self.assertEqual(result["analyzed"], 2)
        self.assertEqual(result["qualified"], 2)
        self.assertEqual(result["by_subreddit"], {"freelance": 2})
        self.assertEqual(len(result["posts"]), 2)
        self.assertEqual(result["posts"][0]["subreddit"], "freelance")

    def test_openclaw_failure_falls_back_to_reddit_public_with_diagnostics(self):
        fallback_summary = {
            "analyzed": 1,
            "qualified": 1,
            "by_subreddit": {"smallbusiness": 1},
            "posts": [
                {
                    "title": "fallback",
                    "subreddit": "smallbusiness",
                    "pain_score": 75,
                    "intent_type": "operations",
                    "urgency_level": "high",
                }
            ],
        }

        with patch("core.openclaw_agent.OpenClawRedditScanner.scan", side_effect=RuntimeError("runner timeout")), patch.object(
            self.control, "run_reddit_public_scan", return_value=fallback_summary
        ) as reddit_public_scan:
            result = self.control.run_reddit_scan()

        reddit_public_scan.assert_called_once()
        self.assertEqual(result["analyzed"], 1)
        self.assertEqual(result["qualified"], 1)
        self.assertEqual(result["by_subreddit"], {"smallbusiness": 1})
        self.assertIn("diagnostics", result)
        self.assertEqual(result["diagnostics"]["source"], "openclaw")
        self.assertEqual(result["diagnostics"]["fallback_to"], "reddit_public")
        self.assertIn("runner timeout", result["diagnostics"]["error"])


if __name__ == "__main__":
    unittest.main()
