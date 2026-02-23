import tempfile
import unittest
from unittest.mock import patch

from core.creator_intelligence import CreatorPainClassifier
from core.migrations.runner import run_migrations
from core.storage import Storage


class CreatorPainClassifierTest(unittest.TestCase):
    def test_classify_signal_detects_category_urgency_and_level(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                classifier = CreatorPainClassifier(storage)

                result = classifier.classify_signal(
                    {
                        "post_text": "I am desperate, need help ASAP with brand deals and pricing. I'm paid $500/month"
                    }
                )

                self.assertEqual(result["pain_category"], "brand_deals")
                self.assertEqual(result["monetization_level"], "high")
                self.assertGreaterEqual(result["urgency_score"], 0.8)

    def test_analyze_unprocessed_signals_inserts_without_mutating_signals(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)

                with storage._lock:
                    storage.conn.execute(
                        """
                        INSERT INTO reddit_signals (
                            id, subreddit, post_url, post_text, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "sig-1",
                            "UGCcreators",
                            "https://reddit.com/r/ugc/sig-1",
                            "Struggling to negotiate contract with a brand",
                            "pending",
                            "2026-01-01T00:00:00+00:00",
                            "2026-01-01T00:00:00+00:00",
                        ),
                    )
                    storage.conn.commit()

                classifier = CreatorPainClassifier(storage)
                inserted = classifier.analyze_unprocessed_signals(limit=10)

                self.assertEqual(len(inserted), 1)
                self.assertEqual(inserted[0]["reddit_signal_id"], "sig-1")
                self.assertEqual(inserted[0]["pain_category"], "negotiation")

                with storage._lock:
                    status = storage.conn.execute(
                        "SELECT status FROM reddit_signals WHERE id = ?",
                        ("sig-1",),
                    ).fetchone()[0]
                    total_analysis = storage.conn.execute(
                        "SELECT COUNT(*) FROM creator_pain_analysis"
                    ).fetchone()[0]

                self.assertEqual(status, "pending")
                self.assertEqual(total_analysis, 1)


if __name__ == "__main__":
    unittest.main()
