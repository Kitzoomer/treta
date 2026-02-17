import os
import sqlite3
import tempfile
import unittest

from core.reddit_intelligence.models import get_db_path, initialize_sqlite
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
        self.assertEqual(signal["suggested_action"], "value")
        self.assertIn("Suggested action adapted based on historical engagement performance.", signal["reasoning"])
        self.assertGreaterEqual(signal["opportunity_score"], 80)

    def test_implicit_classification(self):
        signal = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling to close brand deals",
            post_url="https://reddit.com/r/creators/implicit-1",
        )

        self.assertEqual(signal["intent_level"], "implicit")
        self.assertEqual(signal["suggested_action"], "value")
        self.assertGreaterEqual(signal["opportunity_score"], 50)
        self.assertLessEqual(signal["opportunity_score"], 75)

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

        self.assertEqual(ordered[0]["id"], high["id"])
        self.assertSetEqual(
            {item["id"] for item in ordered},
            {high["id"], medium["id"], low["id"]},
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


    def test_action_adapts_based_on_performance(self):
        baseline_implicit = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling with client outreach",
            post_url="https://reddit.com/r/creators/implicit-baseline",
        )
        self.service.update_feedback(signal_id=baseline_implicit["id"], karma=20, replies=5)

        adapted_implicit = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling to close brand deals",
            post_url="https://reddit.com/r/creators/implicit-adapted",
        )
        self.assertEqual(adapted_implicit["suggested_action"], "value_plus_mention")

        adapted_direct = self.service.analyze_post(
            subreddit="freelance",
            post_text="Does anyone have a template for a media kit?",
            post_url="https://reddit.com/r/freelance/direct-adapted",
        )
        self.assertEqual(adapted_direct["suggested_action"], "value")

    def test_mention_rate_governor_blocks_excess_mentions(self):
        baseline = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling with outreach baseline",
            post_url="https://reddit.com/r/creators/implicit-governor-baseline",
        )
        self.service.update_feedback(signal_id=baseline["id"], karma=20, replies=5)

        for index in range(4):
            self.service.repository.save_signal(
                {
                    "id": f"governor-seed-{index}",
                    "subreddit": "creators",
                    "post_url": f"https://reddit.com/r/creators/governor-seed-{index}",
                    "post_text": "seed mention",
                    "detected_pain_type": "direct",
                    "opportunity_score": 90,
                    "intent_level": "direct",
                    "suggested_action": "value_plus_mention",
                    "generated_reply": "seed",
                    "mention_used": True,
                }
            )

        blocked = self.service.analyze_post(
            subreddit="creators",
            post_text="I'm struggling to close more deals",
            post_url="https://reddit.com/r/creators/implicit-governor-blocked",
        )
        self.assertEqual(blocked["suggested_action"], "value")
        self.assertIn("Global mention cap applied.", blocked["reasoning"])

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
