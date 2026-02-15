import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.ipc_http import start_http_server
from core.product_launch_store import ProductLaunchStore
from core.product_proposal_store import ProductProposalStore


class GumroadSyncEndpointTest(unittest.TestCase):
    def _store(self, root: Path) -> ProductLaunchStore:
        proposals = ProductProposalStore(path=root / "product_proposals.json")
        return ProductLaunchStore(proposal_store=proposals, path=root / "product_launches.json")

    def test_missing_access_token_returns_400(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            launches = self._store(Path(tmp_dir))
            server = start_http_server(host="127.0.0.1", port=0, product_launch_store=launches)
            prev = os.environ.pop("GUMROAD_ACCESS_TOKEN", None)
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
                self.assertIn("Missing Gumroad access token", payload["error"])
            finally:
                if prev is not None:
                    os.environ["GUMROAD_ACCESS_TOKEN"] = prev
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
