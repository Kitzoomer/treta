import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

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

    def test_subreddit_performance_adjusts_score(self):
        for index in range(3):
            self.service.repository.save_signal(
                {
                    "id": f"subreddit-high-{index}",
                    "subreddit": "A",
                    "post_url": f"https://reddit.com/r/A/high-{index}",
                    "post_text": "seed high",
                    "detected_pain_type": "direct",
                    "opportunity_score": 90,
                    "intent_level": "direct",
                    "suggested_action": "value",
                    "generated_reply": "seed",
                    "performance_score": 30,
                    "mention_used": False,
                }
            )

        for index in range(3):
            self.service.repository.save_signal(
                {
                    "id": f"subreddit-low-{index}",
                    "subreddit": "B",
                    "post_url": f"https://reddit.com/r/B/low-{index}",
                    "post_text": "seed low",
                    "detected_pain_type": "direct",
                    "opportunity_score": 90,
                    "intent_level": "direct",
                    "suggested_action": "value",
                    "generated_reply": "seed",
                    "performance_score": 1,
                    "mention_used": False,
                }
            )

        with patch("core.reddit_intelligence.service.random.randint", return_value=85), patch(
            "core.reddit_intelligence.service.SalesInsightService.get_high_performing_keywords",
            return_value=[],
        ):
            high_signal = self.service.analyze_post(
                subreddit="A",
                post_text="Need help with a launch template",
                post_url="https://reddit.com/r/A/new-1",
            )
            low_signal = self.service.analyze_post(
                subreddit="B",
                post_text="Need help with a launch template",
                post_url="https://reddit.com/r/B/new-1",
            )

        self.assertEqual(high_signal["opportunity_score"], 93)
        self.assertIn("Boosted due to high-performing subreddit.", high_signal["reasoning"])
        self.assertEqual(low_signal["opportunity_score"], 80)
        self.assertIn("Reduced due to low-performing subreddit.", low_signal["reasoning"])

    def test_daily_top_actions_limits_and_diversifies(self):
        records = [
            ("a-1", "A", 99, "value"),
            ("a-2", "A", 98, "value_plus_mention"),
            ("a-3", "A", 97, "value"),
            ("b-1", "B", 96, "value"),
            ("b-2", "B", 95, "value"),
            ("c-1", "C", 94, "value"),
            ("c-2", "C", 93, "value"),
            ("ignore-1", "D", 100, "ignore"),
        ]

        for index, (signal_id, subreddit, score, action) in enumerate(records):
            self.service.repository.save_signal(
                {
                    "id": signal_id,
                    "subreddit": subreddit,
                    "post_url": f"https://reddit.com/r/{subreddit}/{signal_id}",
                    "post_text": "seed",
                    "detected_pain_type": "direct",
                    "opportunity_score": score,
                    "intent_level": "direct",
                    "suggested_action": action,
                    "generated_reply": "seed",
                    "status": "pending",
                    "created_at": f"2026-01-01T00:00:0{index}+00:00",
                    "mention_used": action == "value_plus_mention",
                }
            )

        selected = self.service.get_daily_top_actions(limit=5)

        self.assertEqual(len(selected), 5)

        by_subreddit = {}
        for item in selected:
            by_subreddit[item["subreddit"]] = by_subreddit.get(item["subreddit"], 0) + 1
        self.assertTrue(all(count <= 2 for count in by_subreddit.values()))

        self.assertEqual(
            [item["opportunity_score"] for item in selected],
            [99, 98, 96, 95, 94],
        )

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
