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

    def test_dynamic_revenue_bonus_growth(self):
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
            control.subreddit_performance_store.record_sale("freelance", 20.0)
            low_bonus = control._compute_ranking_bonuses("freelance")["revenue_bonus"]
            control.subreddit_performance_store.record_sale("freelance", 100.0)
            high_bonus = control._compute_ranking_bonuses("freelance")["revenue_bonus"]

            self.assertGreater(high_bonus, low_bonus)
            self.assertEqual(high_bonus, 50.0)

    def test_conversion_bonus_cap(self):
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
            control.subreddit_performance_store.record_post_attempt("saas")
            control.subreddit_performance_store.record_sale("saas", 10.0)
            control.subreddit_performance_store.record_sale("saas", 15.0)
            bonuses = control._compute_ranking_bonuses("saas")
            self.assertEqual(bonuses["conversion_bonus"], 30.0)

    def test_ranking_prefers_higher_real_revenue(self):
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
            control.subreddit_performance_store.record_sale("highrev", 80.0)
            control.subreddit_performance_store.record_sale("lowrev", 20.0)

            update_config({"subreddits": ["highrev", "lowrev"], "pain_threshold": 60, "source": "reddit_public"})
            posts = [
                {
                    "id": "post-high",
                    "title": "Help with pricing",
                    "selftext": "Need help now",
                    "score": 50,
                    "num_comments": 10,
                    "subreddit": "highrev",
                    "url": "https://reddit.test/post-high",
                },
                {
                    "id": "post-low",
                    "title": "Help with pricing",
                    "selftext": "Need help now",
                    "score": 50,
                    "num_comments": 10,
                    "subreddit": "lowrev",
                    "url": "https://reddit.test/post-low",
                },
            ]
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.control.compute_pain_score",
                return_value={"pain_score": 80, "intent_type": "purchase_ready", "urgency_level": "high"},
            ):
                result = control.run_reddit_public_scan()

            self.assertEqual(result["posts"][0]["subreddit"], "highrev")
            self.assertGreater(result["posts"][0]["revenue_bonus"], result["posts"][1]["revenue_bonus"])

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
            self.assertEqual(scored["revenue_bonus"], 50.0)
            self.assertEqual(scored["execution_bonus"], 0.0)
            self.assertEqual(scored["conversion_bonus"], 10.0)
            self.assertEqual(scored["roi_priority_bonus"], 50.0)
            self.assertEqual(scored["zero_roi_penalty"], 0.0)
            self.assertEqual(scored["throttle_penalty"], 0.0)
            self.assertEqual(scored["score"], 140.0)

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
