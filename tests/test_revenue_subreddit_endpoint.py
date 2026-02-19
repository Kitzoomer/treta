import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.ipc_http import start_http_server
from core.subreddit_performance_store import SubredditPerformanceStore


class RevenueSubredditEndpointTest(unittest.TestCase):
    def test_revenue_subreddit_endpoint_returns_expected_shape(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SubredditPerformanceStore(path=Path(tmp_dir) / "subreddit_performance.json")
            for _ in range(10):
                store.record_post_attempt("freelance")
            for _ in range(3):
                store.record_plan_executed("freelance")
            store.record_sale("freelance", 29.0)

            server = start_http_server(host="127.0.0.1", port=0, subreddit_performance_store=store)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/revenue/subreddits", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(payload["ok"])
                rows = payload["data"]["subreddits"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["name"], "freelance")
                self.assertEqual(rows[0]["posts_attempted"], 10)
                self.assertEqual(rows[0]["plans_executed"], 3)
                self.assertEqual(rows[0]["sales"], 1)
                self.assertEqual(rows[0]["revenue"], 29.0)
                self.assertEqual(rows[0]["conversion_rate"], 0.1)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
