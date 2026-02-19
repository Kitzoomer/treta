import tempfile
import unittest
from pathlib import Path

from core.revenue_attribution.store import RevenueAttributionStore


class RevenueAttributionStoreTest(unittest.TestCase):
    def test_revenue_store_record_sale_updates_totals(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RevenueAttributionStore(path=Path(tmp_dir) / "revenue_attribution.json")
            store.upsert_tracking(
                tracking_id="treta-abc123-1700000000",
                proposal_id="proposal-1",
                subreddit="r/test",
                price=29,
                created_at="2026-01-01T00:00:00Z",
            )

            store.record_sale("treta-abc123-1700000000", sale_count=2, revenue_delta=58.0, sold_at="2026-01-01T01:00:00Z")
            summary = store.summary()

            self.assertEqual(summary["totals"]["sales"], 2)
            self.assertEqual(summary["totals"]["revenue"], 58.0)
            self.assertEqual(summary["by_proposal"]["proposal-1"]["sales"], 2)
            self.assertEqual(summary["by_subreddit"]["r/test"]["revenue"], 58.0)
            self.assertEqual(summary["by_channel"]["reddit"]["sales"], 2)


if __name__ == "__main__":
    unittest.main()
