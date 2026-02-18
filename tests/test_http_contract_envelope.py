import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.control import Control
from core.ipc_http import start_http_server


class _OkStore:
    def __init__(self, items):
        self._items = items

    def list(self, *args, **kwargs):
        return self._items


class _BoomStore:
    def list(self, *args, **kwargs):
        raise RuntimeError("boom")


class _CrashControl(Control):
    def consume(self, _event):
        raise RuntimeError("unexpected boom")


class HttpContractEnvelopeTest(unittest.TestCase):
    def test_success_response_contains_ok_true_and_data(self):
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=_OkStore([]),
            product_plan_store=_OkStore([]),
            product_launch_store=_OkStore([]),
        )
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertTrue(payload["ok"])
            self.assertIn("data", payload)
        finally:
            server.shutdown()
            server.server_close()

    def test_client_error_uses_client_error_type(self):
        server = start_http_server(host="127.0.0.1", port=0, control=Control())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 404)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "client_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_unexpected_exception_returns_500_server_error(self):
        server = start_http_server(host="127.0.0.1", port=0, control=_CrashControl())
        try:
            req = Request(
                f"http://127.0.0.1:{server.server_port}/product_proposals/abc/approve",
                data=b"{}",
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as ctx:
                urlopen(req, timeout=2)

            self.assertEqual(ctx.exception.code, 500)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "server_error")
        finally:
            server.shutdown()
            server.server_close()

    def test_store_failure_returns_503_dependency_error(self):
        server = start_http_server(
            host="127.0.0.1",
            port=0,
            product_proposal_store=_BoomStore(),
            product_plan_store=_BoomStore(),
            product_launch_store=_BoomStore(),
        )
        try:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(f"http://127.0.0.1:{server.server_port}/system/integrity", timeout=2)

            self.assertEqual(ctx.exception.code, 503)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["type"], "dependency_error")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
