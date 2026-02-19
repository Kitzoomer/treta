import json
import unittest
from urllib.request import urlopen
from unittest.mock import patch

from core.ipc_http import start_http_server


class _Store:
    def list(self, *args, **kwargs):
        return []


class IntegrityCacheTest(unittest.TestCase):
    def test_cache_hit_within_ttl(self):
        store = _Store()
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=store,
            product_plan_store=store,
            product_launch_store=store,
        )
        try:
            with patch("core.ipc_http.compute_system_integrity", return_value={"score": 1}) as mocked:
                with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2):
                    pass
                with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(payload["data"]["metrics"]["integrity_cache_hit"], 1)
        finally:
            server.shutdown()
            server.server_close()

    def test_recompute_failure_returns_last_known_good_snapshot(self):
        store = _Store()
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=store,
            product_plan_store=store,
            product_launch_store=store,
        )
        try:
            with patch("core.ipc_http.compute_system_integrity", return_value={"score": 42}):
                with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2):
                    pass

            server.integrity_cache_ttl_seconds = 0

            with patch("core.ipc_http.compute_system_integrity", side_effect=RuntimeError("boom")):
                with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["score"], 42)
            self.assertTrue(payload["data"]["stale"])
            self.assertTrue(payload["data"]["recompute_failed"])
            self.assertIn("metrics", payload["data"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
