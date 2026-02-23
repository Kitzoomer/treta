import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.creator_intelligence import CreatorProductSuggester
from core.migrations.runner import run_migrations
from core.storage import Storage


class CreatorProductSuggesterTest(unittest.TestCase):
    def test_generate_suggestions_aggregates_pains(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "memory" / "treta.sqlite"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(db_path) as conn:
                run_migrations(conn)
                conn.executemany(
                    """
                    INSERT INTO creator_pain_analysis (
                        id, reddit_signal_id, pain_category, monetization_level, urgency_score, analyzed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("a-1", "s-1", "pricing", "low", 0.2, "2026-01-01T00:00:00+00:00"),
                        ("a-2", "s-2", "pricing", "low", 0.8, "2026-01-01T00:00:00+00:00"),
                        ("a-3", "s-3", "brand_deals", "high", 0.9, "2026-01-01T00:00:00+00:00"),
                    ],
                )
                conn.commit()

            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                suggester = CreatorProductSuggester(storage=storage)
                generated = suggester.generate_suggestions()

            by_category = {item["pain_category"]: item for item in generated}
            self.assertEqual(by_category["pricing"]["frequency"], 2)
            self.assertAlmostEqual(by_category["pricing"]["avg_urgency"], 0.5)
            self.assertEqual(by_category["pricing"]["suggested_product"], "Pricing Calculator + Rate Guide")
            self.assertEqual(by_category["pricing"]["estimated_price_range"], "19-29")
            self.assertEqual(by_category["brand_deals"]["estimated_price_range"], "59-149")


if __name__ == "__main__":
    unittest.main()
