import tempfile
import unittest
from pathlib import Path

from core.subreddit_performance_store import SubredditPerformanceStore


class SubredditPerformanceStoreTest(unittest.TestCase):
    def test_records_and_persists_subreddit_metrics(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "subreddit_performance.json"
            store = SubredditPerformanceStore(path=path)

            store.record_post_attempt("freelance")
            store.record_proposal_generated("freelance")
            store.record_plan_executed("freelance")
            store.record_sale("freelance", 19.5)

            stats = store.get_subreddit_stats("freelance")
            self.assertEqual(stats["posts_attempted"], 1)
            self.assertEqual(stats["proposals_generated"], 1)
            self.assertEqual(stats["plans_executed"], 1)
            self.assertEqual(stats["sales"], 1)
            self.assertEqual(stats["revenue"], 19.5)

            reloaded = SubredditPerformanceStore(path=path)
            self.assertEqual(reloaded.get_subreddit_stats("freelance")["sales"], 1)
            summary = reloaded.get_summary()
            self.assertEqual(len(summary["subreddits"]), 1)
            self.assertEqual(summary["subreddits"][0]["name"], "freelance")


if __name__ == "__main__":
    unittest.main()
