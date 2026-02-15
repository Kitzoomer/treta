import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from unittest.mock import patch

from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore




class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class GumroadSyncEndpointTest(unittest.TestCase):
    def _store(self, root: Path) -> ProductLaunchStore:
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        return ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")


    def test_auth_endpoint_redirects_to_gumroad_authorize(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            launches = self._store(root)
            previous = {
                "TRETA_DATA_DIR": os.environ.get("TRETA_DATA_DIR"),
                "GUMROAD_CLIENT_ID": os.environ.get("GUMROAD_CLIENT_ID"),
                "GUMROAD_REDIRECT_URI": os.environ.get("GUMROAD_REDIRECT_URI"),
            }
            os.environ["TRETA_DATA_DIR"] = str(root)
            os.environ["GUMROAD_CLIENT_ID"] = "client-123"
            os.environ["GUMROAD_REDIRECT_URI"] = "http://localhost:7777/gumroad/callback"
            server = start_http_server(host="127.0.0.1", port=0, product_launch_store=launches)
            try:
                opener = build_opener(_NoRedirectHandler())
                req = Request(f"http://127.0.0.1:{server.server_port}/gumroad/auth")
                with self.assertRaises(HTTPError) as ctx:
                    opener.open(req, timeout=2)

                self.assertEqual(ctx.exception.code, 302)
                location = ctx.exception.headers.get("Location", "")
                self.assertTrue(location.startswith("https://gumroad.com/oauth/authorize?"))
                self.assertIn("client_id=client-123", location)
                self.assertIn("response_type=code", location)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                server.shutdown()
                server.server_close()

    def test_sync_sales_without_stored_token_returns_400(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            launches = self._store(root)
            prev_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = str(root)
            server = start_http_server(host="127.0.0.1", port=0, product_launch_store=launches)
            try:
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/gumroad/sync_sales",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req, timeout=2)
                self.assertEqual(ctx.exception.code, 400)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(payload["error"], "Gumroad not connected. Visit /gumroad/auth first.")
            finally:
                if prev_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = prev_data_dir
                server.shutdown()
                server.server_close()

    @patch("core.ipc_http.exchange_code_for_token")
    def test_callback_exchanges_code_and_saves_token(self, mock_exchange):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            launches = self._store(root)
            prev_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = str(root)
            mock_exchange.return_value = "token-from-oauth"
            server = start_http_server(host="127.0.0.1", port=0, product_launch_store=launches)
            try:
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/gumroad/callback?code=oauth-code",
                    timeout=2,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(payload, {"status": "connected"})
                mock_exchange.assert_called_once_with("oauth-code")
                token_file = root / "gumroad_oauth_token.json"
                stored = json.loads(token_file.read_text(encoding="utf-8"))
                self.assertEqual(stored["access_token"], "token-from-oauth")
            finally:
                if prev_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = prev_data_dir
                server.shutdown()
                server.server_close()

    @patch("core.integrations.gumroad_client.requests.get")
    def test_sync_sales_with_token_uses_gumroad_client(self, mock_get):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals = ProductProposalStore(path=root / "product_proposals.json")
            launches = ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")
            proposals.add({"id": "proposal-1", "product_name": "Product"})
            launch = launches.add_from_proposal("proposal-1")
            launches.link_gumroad_product(launch["id"], "gumroad-product")

            prev_data_dir = os.environ.get("TRETA_DATA_DIR")
            os.environ["TRETA_DATA_DIR"] = str(root)
            (root / "gumroad_oauth_token.json").write_text(
                json.dumps({"access_token": "stored-token"}),
                encoding="utf-8",
            )

            response = unittest.mock.Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "sales": [
                    {"id": "sale-1", "price": "9.99", "created_at": "2026-01-01T00:00:00Z"}
                ]
            }
            mock_get.return_value = response

            server = start_http_server(host="127.0.0.1", port=0, product_launch_store=launches)
            try:
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/gumroad/sync_sales",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=2) as http_response:
                    payload = json.loads(http_response.read().decode("utf-8"))

                self.assertEqual(payload["new_sales"], 1)
                mock_get.assert_called_once_with(
                    "https://api.gumroad.com/v2/sales",
                    params={"product_id": "gumroad-product"},
                    headers={"Authorization": "Bearer stored-token"},
                    timeout=10,
                )
            finally:
                if prev_data_dir is None:
                    os.environ.pop("TRETA_DATA_DIR", None)
                else:
                    os.environ["TRETA_DATA_DIR"] = prev_data_dir
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
