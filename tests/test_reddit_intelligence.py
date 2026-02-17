import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.reddit_intelligence.models import get_db_path, initialize_sqlite
from core.reddit_intelligence.router import RedditIntelligenceRouter
from core.reddit_intelligence.service import RedditIntelligenceService


class RedditIntelligenceTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._previous_data_dir = os.environ.get("TRETA_DATA_DIR")
        os.environ["TRETA_DATA_DIR"] = self._tmp_dir.name
        initialize_sqlite()
        self.service = RedditIntelligenceService()

    def tearDown(self):
        db_path = get_db_path()
        if db_path.exists():
            db_path.unlink()

        if self._previous_data_dir is None:
            os.environ.pop("TRETA_DATA_DIR", None)
        else:
            os.environ["TRETA_DATA_DIR"] = self._previous_data_dir

        self._tmp_dir.cleanup()

    def test_direct_classification(self):
        signal = self.service.analyze_post(
            subreddit="freelance",
            post_text="Does anyone have a template for a media kit?",
            post_url="https://reddit.com/r/freelance/direct-1",
        )

        self.assertEqual(signal["intent_level"], "direct")
        self.assertEqual(signal["suggested_action"], "value_plus_mention")
        self.assertGreaterEqual(signal["opportunity_score"], 75)

    def test_implicit_classification(self):
        signal = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling to close brand deals",
            post_url="https://reddit.com/r/creators/implicit-1",
        )

        self.assertEqual(signal["intent_level"], "implicit")
        self.assertEqual(signal["suggested_action"], "value")
        self.assertGreaterEqual(signal["opportunity_score"], 45)
        self.assertLessEqual(signal["opportunity_score"], 70)

    def test_trend_classification(self):
        signal = self.service.analyze_post(
            subreddit="creators",
            post_text="Interesting discussion about creators",
            post_url="https://reddit.com/r/creators/trend-1",
        )

        self.assertEqual(signal["intent_level"], "trend")
        self.assertEqual(signal["suggested_action"], "ignore")

    def test_persistence(self):
        signal = self.service.analyze_post(
            subreddit="startups",
            post_text="Need help choosing a pricing model",
            post_url="https://reddit.com/r/startups/persist-1",
        )

        conn = sqlite3.connect(get_db_path())
        try:
            row = conn.execute(
                "SELECT id, subreddit, status FROM reddit_signals WHERE id = ?",
                (signal["id"],),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], signal["id"])
        self.assertEqual(row[1], "startups")
        self.assertEqual(row[2], "pending")

        conn = sqlite3.connect(get_db_path())
        try:
            feedback_row = conn.execute(
                "SELECT karma, replies, performance_score FROM reddit_signals WHERE id = ?",
                (signal["id"],),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(feedback_row[0], 0)
        self.assertEqual(feedback_row[1], 0)
        self.assertEqual(feedback_row[2], 0)

    def test_list_top_pending(self):
        low = self.service.analyze_post(
            subreddit="entrepreneur",
            post_text="Interesting discussion about creators",
            post_url="https://reddit.com/r/entrepreneur/low",
        )
        medium = self.service.analyze_post(
            subreddit="entrepreneur",
            post_text="I'm struggling to close brand deals",
            post_url="https://reddit.com/r/entrepreneur/medium",
        )
        high = self.service.analyze_post(
            subreddit="entrepreneur",
            post_text="Does anyone have a template for a media kit?",
            post_url="https://reddit.com/r/entrepreneur/high",
        )

        ordered = self.service.list_top_pending(limit=3)

        self.assertEqual(
            [item["id"] for item in ordered],
            [high["id"], medium["id"], low["id"]],
        )
        self.assertEqual(
            [item["opportunity_score"] for item in ordered],
            sorted(
                [
                    low["opportunity_score"],
                    medium["opportunity_score"],
                    high["opportunity_score"],
                ],
                reverse=True,
            ),
        )


    def test_sales_boost_applied(self):
        with patch("core.reddit_intelligence.service.SalesInsightService.get_high_performing_keywords", return_value=["media", "kit"]), patch("core.reddit_intelligence.service.random.randint", side_effect=[90, 15]):
            signal = self.service.analyze_post(
                subreddit="freelance",
                post_text="Does anyone have a template for a media kit?",
                post_url="https://reddit.com/r/freelance/boost-1",
            )

        self.assertGreaterEqual(signal["opportunity_score"], 95)
        self.assertLessEqual(signal["opportunity_score"], 100)
        self.assertIn(
            "Boosted score due to alignment with high-performing product keywords.",
            signal.get("reasoning", ""),
        )

    def test_feedback_learning_adjusts_score(self):
        with patch(
            "core.reddit_intelligence.service.SalesInsightService.get_high_performing_keywords",
            return_value=[],
        ), patch("core.reddit_intelligence.service.random.randint", return_value=80):
            first_signal = self.service.analyze_post(
                subreddit="freelance",
                post_text="Does anyone have a template for a media kit?",
                post_url="https://reddit.com/r/freelance/feedback-base",
            )

            updated_feedback = self.service.update_feedback(
                signal_id=first_signal["id"],
                karma=12,
                replies=4,
            )

            second_signal = self.service.analyze_post(
                subreddit="freelance",
                post_text="Need help with a template for brand outreach",
                post_url="https://reddit.com/r/freelance/feedback-next",
            )

        self.assertIsNotNone(updated_feedback)
        self.assertEqual(updated_feedback["performance_score"], 20)
        self.assertGreater(second_signal["opportunity_score"], first_signal["opportunity_score"])
        self.assertIn(
            "Adjusted based on historical Reddit performance.",
            second_signal.get("reasoning", ""),
        )

    def test_feedback_patch_endpoint(self):
        signal = self.service.analyze_post(
            subreddit="freelance",
            post_text="Need help with a template",
            post_url="https://reddit.com/r/freelance/feedback-endpoint",
        )

        router = RedditIntelligenceRouter(service=self.service)
        status, payload = router.handle_patch(
            f"/reddit/signals/{signal['id']}/feedback",
            {"karma": 5, "replies": 3},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["karma"], 5)
        self.assertEqual(payload["replies"], 3)
        self.assertEqual(payload["performance_score"], 11)

    def test_update_status(self):
        signal = self.service.analyze_post(
            subreddit="saas",
            post_text="Need help with a sales template",
            post_url="https://reddit.com/r/saas/update-1",
        )

        updated = self.service.update_status(signal_id=signal["id"], status="approved")

        self.assertIsNotNone(updated)
        self.assertEqual(updated["id"], signal["id"])
        self.assertEqual(updated["status"], "approved")


if __name__ == "__main__":
    unittest.main()
