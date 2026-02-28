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

    def _patch(self, server, path: str, payload: dict, headers: dict | None = None):
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        req = Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="PATCH",
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
        with patch.object(ipc_http, "API_TOKEN", "test123"), patch.object(ipc_http, "_auth_mode_warned", False):
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

    def test_dev_mode_allows_protected_endpoint_without_token(self):
        with (
            patch.object(ipc_http, "API_TOKEN", None),
            patch.object(ipc_http, "TRETA_DEV_MODE", True),
            patch.object(ipc_http, "TRETA_REQUIRE_TOKEN", True),
            patch.object(ipc_http, "_auth_mode_warned", False),
        ):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, _ = self._post(server, "/opportunities/evaluate", {"id": "opp-1"})
                self.assertEqual(status, 200)
            finally:
                server.shutdown()
                server.server_close()


    def test_patch_endpoint_requires_token_when_configured(self):
        with patch.object(ipc_http, "API_TOKEN", "test123"), patch.object(ipc_http, "_auth_mode_warned", False):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status_no_header, body_no_header = self._patch(
                    server,
                    "/reddit/signals/signal-1/status",
                    {"status": "approved"},
                )
                self.assertEqual(status_no_header, 401)
                self.assertEqual(body_no_header.get("error", {}).get("code"), "unauthorized")

                status_ok, body_ok = self._patch(
                    server,
                    "/reddit/signals/signal-1/status",
                    {"status": "approved"},
                    headers={"Authorization": "Bearer test123"},
                )
                self.assertIn(status_ok, {200, 404})
                self.assertNotEqual(body_ok.get("error", {}).get("code"), "unauthorized")
            finally:
                server.shutdown()
                server.server_close()

    def test_degraded_mode_blocks_mutating_endpoints_without_token(self):
        with (
            patch.object(ipc_http, "API_TOKEN", None),
            patch.object(ipc_http, "TRETA_DEV_MODE", False),
            patch.object(ipc_http, "TRETA_REQUIRE_TOKEN", True),
            patch.object(ipc_http, "_auth_mode_warned", False),
        ):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, body = self._post(server, "/opportunities/evaluate", {"id": "opp-1"})
                self.assertEqual(status, 503)
                self.assertEqual(body.get("error", {}).get("code"), "auth_degraded")

                health_status, health_body = self._get(server, "/health")
                self.assertEqual(health_status, 200)
                self.assertEqual(health_body.get("data", {}).get("status"), "degraded")
            finally:
                server.shutdown()
                server.server_close()

    def test_require_token_disabled_allows_requests_without_token(self):
        with (
            patch.object(ipc_http, "API_TOKEN", None),
            patch.object(ipc_http, "TRETA_DEV_MODE", False),
            patch.object(ipc_http, "TRETA_REQUIRE_TOKEN", False),
            patch.object(ipc_http, "_auth_mode_warned", False),
        ):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, _ = self._post(server, "/opportunities/evaluate", {"id": "opp-1"})
                self.assertEqual(status, 200)
            finally:
                server.shutdown()
                server.server_close()

    def test_payload_too_large_is_rejected(self):
        with patch.object(ipc_http, "API_TOKEN", None), patch.object(ipc_http, "MAX_REQUEST_BODY_BYTES", 64), patch.object(ipc_http, "_auth_mode_warned", False):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, body = self._post(
                    server,
                    "/event",
                    {"type": "RunInfoproductScan", "payload": {"blob": "x" * 512}},
                )
                self.assertEqual(status, 413)
                self.assertEqual(body.get("error", {}).get("code"), "payload_too_large")
            finally:
                server.shutdown()
                server.server_close()

    def test_event_endpoint_rejects_unsupported_event_type(self):
        with patch.object(ipc_http, "API_TOKEN", None), patch.object(ipc_http, "_auth_mode_warned", False):
            server = start_http_server(host="127.0.0.1", port=0)
            try:
                status, body = self._post(
                    server,
                    "/event",
                    {"type": "DeleteEverything", "payload": {}},
                )
                self.assertEqual(status, 400)
                self.assertEqual(body.get("error", {}).get("code"), "unsupported_event_type")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
