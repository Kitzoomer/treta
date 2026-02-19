import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from core.ipc_http import start_http_server
from core.revenue_attribution.store import RevenueAttributionStore


class RevenueSummaryEndpointTest(unittest.TestCase):
    def test_revenue_summary_endpoint_returns_expected_shape(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RevenueAttributionStore(path=Path(tmp_dir) / "revenue_attribution.json")
            store.upsert_tracking("treta-abc123-1700000000", "proposal-1", subreddit="r/python")
            store.record_sale("treta-abc123-1700000000", sale_count=1, revenue_delta=19.0)

            server = start_http_server(host="127.0.0.1", port=0, revenue_attribution_store=store)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/revenue/summary", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertTrue(payload["ok"])
                self.assertIn("totals", payload)
                self.assertIn("by_proposal", payload)
                self.assertIn("by_subreddit", payload)
                self.assertEqual(payload["totals"]["sales"], 1)
                self.assertEqual(payload["by_proposal"]["proposal-1"]["revenue"], 19.0)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
