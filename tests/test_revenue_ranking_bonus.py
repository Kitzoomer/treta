import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.control import Control
from core.events import Event
from core.opportunity_store import OpportunityStore
from core.product_launch_store import ProductLaunchStore
from core.product_plan_store import ProductPlanStore
from core.product_proposal_store import ProductProposalStore
from core.reddit_public.config import update_config
from core.subreddit_performance_store import SubredditPerformanceStore


class RevenueRankingBonusTest(unittest.TestCase):

    def test_roi_calculation_basic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
            )
            stats = {"posts_attempted": 4, "revenue": 80.0}
            self.assertEqual(control._compute_subreddit_roi(stats), 20.0)
            self.assertEqual(control._compute_subreddit_roi({"posts_attempted": 0, "revenue": 100.0}), 0.0)

    def test_high_roi_bonus_applied(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
            )
            for _ in range(2):
                control.subreddit_performance_store.record_post_attempt("freelance")
            control.subreddit_performance_store.record_sale("freelance", 50.0)
            bonuses = control._compute_ranking_bonuses("freelance")
            self.assertEqual(bonuses["roi_priority_bonus"], 30)

    def test_zero_sales_penalty_after_threshold(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
            )
            for _ in range(3):
                control.subreddit_performance_store.record_post_attempt("saas")
            bonuses = control._compute_ranking_bonuses("saas")
            self.assertEqual(bonuses["zero_roi_penalty"], -20)

    def test_throttle_applied_after_5_failed_attempts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
            )
            control._reddit_posts_path = lambda: root / "reddit_posts.json"
            for _ in range(5):
                control.subreddit_performance_store.record_post_attempt("deadsub")

            update_config({"subreddits": ["deadsub"], "pain_threshold": 60, "source": "reddit_public"})
            posts = [
                {
                    "id": "post-1",
                    "title": "Help with pricing",
                    "selftext": "Need help now",
                    "score": 50,
                    "num_comments": 10,
                    "subreddit": "deadsub",
                    "url": "https://reddit.test/post-1",
                }
            ]
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.control.compute_pain_score",
                return_value={"pain_score": 80, "intent_type": "purchase_ready", "urgency_level": "high"},
            ):
                result = control.run_reddit_public_scan()

            self.assertIn("diagnostics", result)
            self.assertEqual(result["diagnostics"]["throttled_subreddits"], ["deadsub"])
            self.assertEqual(result["posts"][0]["throttle_penalty"], -50)

    def test_scan_score_includes_revenue_execution_and_conversion_bonuses(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            alignment = Mock()
            alignment.evaluate.return_value = {"aligned": True, "alignment_score": 0.9, "reason": "ok"}
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
                alignment_engine=alignment,
            )
            control._reddit_posts_path = lambda: root / "reddit_posts.json"

            for _ in range(10):
                control.subreddit_performance_store.record_post_attempt("freelance")
            for _ in range(3):
                control.subreddit_performance_store.record_plan_executed("freelance")
            control.subreddit_performance_store.record_sale("freelance", 200)

            update_config({"subreddits": ["freelance"], "pain_threshold": 60, "source": "reddit_public"})
            posts = [
                {
                    "id": "post-1",
                    "title": "Help with pricing",
                    "selftext": "Need help now",
                    "score": 50,
                    "num_comments": 10,
                    "subreddit": "freelance",
                    "url": "https://reddit.test/post-1",
                }
            ]

            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.control.compute_pain_score",
                return_value={"pain_score": 80, "intent_type": "purchase_ready", "urgency_level": "high"},
            ):
                result = control.run_reddit_public_scan()

            scored = result["posts"][0]
            self.assertEqual(scored["revenue_bonus"], 15)
            self.assertEqual(scored["execution_bonus"], 0)
            self.assertEqual(scored["conversion_bonus"], 20)
            self.assertEqual(scored["roi_priority_bonus"], 15)
            self.assertEqual(scored["zero_roi_penalty"], 0)
            self.assertEqual(scored["throttle_penalty"], 0)
            self.assertEqual(scored["score"], 115)

    def test_proposal_generation_records_subreddit_metric(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposal_store = ProductProposalStore(path=root / "product_proposals.json")
            alignment = Mock()
            alignment.evaluate.return_value = {"aligned": True, "alignment_score": 0.9, "reason": "ok"}
            control = Control(
                opportunity_store=OpportunityStore(path=root / "opportunities.json"),
                product_proposal_store=proposal_store,
                product_plan_store=ProductPlanStore(path=root / "product_plans.json"),
                product_launch_store=ProductLaunchStore(proposal_store=proposal_store, path=root / "product_launches.json"),
                subreddit_performance_store=SubredditPerformanceStore(path=root / "subreddit_performance.json"),
                alignment_engine=alignment,
            )

            control.consume(
                Event(
                    type="OpportunityDetected",
                    payload={"id": "opp-1", "source": "reddit_public", "title": "Need proposal", "subreddit": "saas", "opportunity": {}},
                    source="test",
                )
            )

            stats = control.subreddit_performance_store.get_subreddit_stats("saas")
            self.assertEqual(stats["proposals_generated"], 1)


if __name__ == "__main__":
    unittest.main()
