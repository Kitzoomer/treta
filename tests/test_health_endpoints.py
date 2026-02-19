import json
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from core.ipc_http import start_http_server


class _Store:
    def list(self, *args, **kwargs):
        return []


class HealthEndpointsTest(unittest.TestCase):
    def test_live_endpoint_is_always_200(self):
        server = start_http_server(host="127.0.0.1", port=0)
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/health/live", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["status"], "live")
        finally:
            server.shutdown()
            server.server_close()

    def test_ready_endpoint_reports_dependency_error_when_not_ready(self):
        server = start_http_server(host="127.0.0.1", port=0)
        try:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{server.server_port}/health/ready", timeout=2)

            self.assertEqual(ctx.exception.code, 503)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "dependency_error")
            self.assertIn("checks", payload["error"]["details"])
        finally:
            server.shutdown()
            server.server_close()

    def test_ready_endpoint_is_200_when_dependencies_wired(self):
        store = _Store()
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=store,
            product_plan_store=store,
            product_launch_store=store,
            control=object(),
        )
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/health/ready", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["data"]["status"], "ready")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
