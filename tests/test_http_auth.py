import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import core.ipc_http as ipc_http
from core.ipc_http import start_http_server


class HttpAuthTest(unittest.TestCase):
    def _post(self, server, path: str, payload: dict, headers: dict | None = None):
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        req = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=req_headers,
        )
        try:
            with urlopen(req, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            return exc.code, body

    def _get(self, server, path: str, headers: dict | None = None):
        req = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            method="GET",
            headers=headers or {},
        )
        try:
            with urlopen(req, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            return exc.code, body

    def test_protected_endpoint_requires_token_when_configured(self):
        with patch.object(ipc_http, "API_TOKEN", "test123"), patch.object(ipc_http, "_auth_dev_mode_warned", False):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status_no_header, body_no_header = self._post(server, "/opportunities/evaluate", {"id": "opp-1"})
                self.assertEqual(status_no_header, 401)
                self.assertEqual(body_no_header.get("error", {}).get("code"), "unauthorized")

                status_wrong, body_wrong = self._post(
                    server,
                    "/opportunities/evaluate",
                    {"id": "opp-1"},
                    headers={"Authorization": "Bearer wrong"},
                )
                self.assertEqual(status_wrong, 401)
                self.assertEqual(body_wrong.get("error", {}).get("code"), "unauthorized")

                status_ok, _ = self._post(
                    server,
                    "/opportunities/evaluate",
                    {"id": "opp-1"},
                    headers={"Authorization": "Bearer test123"},
                )
                self.assertEqual(status_ok, 200)
            finally:
                server.shutdown()
                server.server_close()

    def test_dev_permissive_mode_does_not_block_protected_endpoint(self):
        with patch.object(ipc_http, "API_TOKEN", None), patch.object(ipc_http, "_auth_dev_mode_warned", False):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, _ = self._get(server, "/strategy/decide")
                self.assertNotEqual(status, 401)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
