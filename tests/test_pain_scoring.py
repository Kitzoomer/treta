import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.bus import EventBus
from core.control import Control
from core.product_proposal_store import ProductProposalStore
from core.events import Event
from core.reddit_public.config import DEFAULT_CONFIG, update_config
from core.reddit_public.pain_scoring import compute_pain_score
from core.revenue_attribution.store import RevenueAttributionStore


class PainScoringTest(unittest.TestCase):
    def setUp(self):
        update_config(DEFAULT_CONFIG.copy())

    def tearDown(self):
        update_config(DEFAULT_CONFIG.copy())

    def test_multiple_keywords_scores_above_70(self):
        post = {
            "title": "How do I fix client pricing?",
            "selftext": "I am struggling and confused about proposal rate and need help",
            "score": 12,
            "num_comments": 16,
        }

        result = compute_pain_score(post)

        self.assertGreater(result["pain_score"], 70)
        self.assertEqual(result["intent_type"], "monetization")

    def test_without_keywords_scores_below_30(self):
        post = {
            "title": "Sharing my weekly progress",
            "selftext": "Finished editing videos and had a good week.",
            "score": 7,
            "num_comments": 1,
        }

        result = compute_pain_score(post)

        self.assertLess(result["pain_score"], 30)
        self.assertEqual(result["intent_type"], "general")
        self.assertEqual(result["urgency_level"], "low")

    def test_score_caps_at_100(self):
        post = {
            "title": "How do I help client pricing proposal template asap?",
            "selftext": "I am struggling, stuck, confused, overwhelmed with this issue/problem and need help today",
            "score": 25,
            "num_comments": 50,
        }

        result = compute_pain_score(post)

        self.assertEqual(result["pain_score"], 100)



    def test_disable_engagement_boost_uses_config(self):
        post = {
            "title": "How do I fix this?",
            "selftext": "Need help",
            "score": 12,
            "num_comments": 30,
        }

        update_config({"enable_engagement_boost": False})
        result = compute_pain_score(post)

        self.assertEqual(result["pain_score"], 35)

class RedditPublicPainGateTest(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        update_config(DEFAULT_CONFIG.copy())

    def tearDown(self):
        update_config(DEFAULT_CONFIG.copy())

    def test_only_posts_with_pain_score_60_or_more_emit_opportunity(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        posts = [
            {
                "id": "low",
                "title": "General update",
                "selftext": "Just sharing progress",
                "score": 10,
                "num_comments": 2,
                "subreddit": "freelance",
            },
            {
                "id": "high",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "freelance",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                control.consume(Event(type="RunInfoproductScan", payload={}, source="test"))

        emitted = []
        while True:
            event = self.bus.pop(timeout=0.001)
            if event is None:
                break
            if event.type == "OpportunityDetected":
                emitted.append(event)

        self.assertEqual(len(emitted), 1)
        payload = emitted[0].payload
        self.assertEqual(payload["id"], "reddit-public-high")
        self.assertGreaterEqual(payload["pain_score"], 60)
        self.assertIn("intent_type", payload)
        self.assertIn("urgency_level", payload)





    def test_revenue_bonus_prioritizes_subreddit_with_sales(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        posts = [
            {
                "id": "freelance-post",
                "title": "Need help pricing retainers",
                "selftext": "need help with proposal rate",
                "score": 10,
                "num_comments": 5,
                "subreddit": "r/freelance",
            },
            {
                "id": "other-post",
                "title": "Need help pricing retainers",
                "selftext": "need help with proposal rate",
                "score": 10,
                "num_comments": 5,
                "subreddit": "r/other",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            revenue_store = RevenueAttributionStore(path=Path(temp_dir) / "revenue_attribution.json")
            revenue_store.upsert_tracking("treta-freelance", "proposal-1", subreddit="r/freelance")
            revenue_store.record_sale("treta-freelance", sale_count=1, revenue_delta=20.0)

            control = Control(
                product_proposal_store=proposal_store,
                revenue_attribution_store=revenue_store,
                bus=self.bus,
            )
            control.subreddit_performance_store.record_post_attempt("r/freelance")
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                result = control.run_reddit_public_scan()

        self.assertEqual(result["qualified"], 2)
        self.assertEqual(result["posts"][0]["pain_score"], result["posts"][1]["pain_score"])

        emitted = []
        while True:
            event = self.bus.pop(timeout=0.001)
            if event is None:
                break
            if event.type == "OpportunityDetected":
                emitted.append(event)

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].payload["id"], "reddit-public-freelance-post")
        self.assertEqual(emitted[0].payload["revenue_bonus"], 10.0)
        self.assertGreater(emitted[0].payload["score"], emitted[0].payload["pain_score"])

    def test_scan_emits_only_top_scoring_opportunity(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        posts = [
            {
                "id": "top",
                "title": "How do I fix client pricing asap?",
                "selftext": "I am struggling, stuck, confused and overwhelmed with proposal rates and need help today",
                "score": 3,
                "num_comments": 1,
                "subreddit": "freelance",
            },
            {
                "id": "lower",
                "title": "Need help with pricing",
                "selftext": "need help with client pricing",
                "score": 40,
                "num_comments": 10,
                "subreddit": "freelance",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                result = control.run_reddit_public_scan()

        emitted = []
        while True:
            event = self.bus.pop(timeout=0.001)
            if event is None:
                break
            if event.type == "OpportunityDetected":
                emitted.append(event)

        self.assertEqual(result["qualified"], 2)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].payload["id"], "reddit-public-top")

    def test_scan_does_not_emit_when_active_proposal_exists(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        posts = [
            {
                "id": "high",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "freelance",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            control.product_proposal_store.add(
            {
                "id": "existing-draft",
                "created_at": "2025-01-01T00:00:00+00:00",
                "source_opportunity_id": "opp-existing",
                "product_name": "Existing product",
                "product_type": "template",
                "target_audience": "creators",
                "core_problem": "pricing",
                "solution": "pricing framework",
                "format": "pdf",
                "price_suggestion": "$29",
                "deliverables": ["guide"],
                "positioning": "fast win",
                "distribution_plan": "x",
                "validation_plan": "y",
                "confidence": 7,
                "reasoning": "existing",
                "status": "draft",
            }
        )

            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                control.run_reddit_public_scan()

            emitted = []
            while True:
                event = self.bus.pop(timeout=0.001)
                if event is None:
                    break
                if event.type == "OpportunityDetected":
                    emitted.append(event)

            self.assertEqual(len(emitted), 0)

    def test_scan_summary_includes_by_subreddit_counts(self):
        posts = [
            {
                "id": "high-1",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "freelance",
            },
            {
                "id": "high-2",
                "title": "Need help closing brand deals",
                "selftext": "I am overwhelmed and stuck with this issue",
                "score": 20,
                "num_comments": 9,
                "subreddit": "UGCcreators",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                result = control.run_reddit_public_scan()

        self.assertEqual(result["qualified"], 2)
        self.assertEqual(result["by_subreddit"], {"freelance": 1, "UGCcreators": 1})

    def test_threshold_comes_from_config(self):
        while self.bus.pop(timeout=0.001) is not None:
            pass

        posts = [
            {
                "id": "mid",
                "title": "How do I set pricing?",
                "selftext": "need help",
                "score": 15,
                "num_comments": 5,
                "subreddit": "freelance",
            }
        ]

        update_config({"pain_threshold": 90})

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                result = control.run_reddit_public_scan()

        self.assertEqual(result["qualified"], 0)

    def test_last_scan_is_stored_in_runtime(self):
        posts = [
            {
                "id": "high-1",
                "title": "How do I set client pricing?",
                "selftext": "I am struggling with proposal rate and need help asap",
                "score": 15,
                "num_comments": 6,
                "subreddit": "freelance",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            proposal_store = ProductProposalStore(path=Path(temp_dir) / "product_proposals.json")
            control = Control(product_proposal_store=proposal_store, bus=self.bus)
            with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
                "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
                return_value=[],
            ):
                result = control.run_reddit_public_scan()

        self.assertEqual(control.get_last_reddit_scan(), result)


if __name__ == "__main__":
    unittest.main()
