import unittest
from unittest.mock import patch

from core.bus import event_bus
from core.control import Control
from core.events import Event
from core.reddit_public.config import DEFAULT_CONFIG, update_config
from core.reddit_public.pain_scoring import compute_pain_score


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
        update_config(DEFAULT_CONFIG.copy())

    def tearDown(self):
        update_config(DEFAULT_CONFIG.copy())

    def test_only_posts_with_pain_score_60_or_more_emit_opportunity(self):
        while event_bus.pop(timeout=0.001) is not None:
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

        control = Control()
        with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
            "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
            return_value=[],
        ):
            control.consume(Event(type="RunInfoproductScan", payload={}, source="test"))

        emitted = []
        while True:
            event = event_bus.pop(timeout=0.001)
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

        control = Control()
        with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
            "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
            return_value=[],
        ):
            result = control.run_reddit_public_scan()

        self.assertEqual(result["qualified"], 2)
        self.assertEqual(result["by_subreddit"], {"freelance": 1, "UGCcreators": 1})

    def test_threshold_comes_from_config(self):
        while event_bus.pop(timeout=0.001) is not None:
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

        control = Control()
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

        control = Control()
        with patch("core.reddit_public.service.RedditPublicService.scan_subreddits", return_value=posts), patch(
            "core.reddit_intelligence.service.RedditIntelligenceService.get_daily_top_actions",
            return_value=[],
        ):
            result = control.run_reddit_public_scan()

        self.assertEqual(control.get_last_reddit_scan(), result)


if __name__ == "__main__":
    unittest.main()
