import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.control import Control
from core.product_launch_store import ProductLaunchStore
from core.product_plan_store import ProductPlanStore
from core.product_proposal_store import ProductProposalStore
from core.ipc_http import start_http_server


class HttpInvariantEnforcementTest(unittest.TestCase):
    def test_execute_endpoint_returns_server_error_when_global_invariants_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            proposal_store = ProductProposalStore(path=data_dir / "product_proposals.json")
            plan_store = ProductPlanStore(path=data_dir / "product_plans.json")
            launch_store = ProductLaunchStore(proposal_store=proposal_store, path=data_dir / "product_launches.json")
            control = Control(
                product_proposal_store=proposal_store,
                product_plan_store=plan_store,
                product_launch_store=launch_store,
            )

            proposal_store.add({"id": "proposal-1", "status": "approved", "product_name": "A"})
            proposal_store.add({"id": "proposal-2", "status": "building", "product_name": "B"})
            proposal_store.add({"id": "proposal-3", "status": "ready_to_launch", "product_name": "C"})

            server = start_http_server(
                host="127.0.0.1",
                port=0,
                control=control,
                product_proposal_store=proposal_store,
                product_plan_store=plan_store,
                product_launch_store=launch_store,
            )
            try:
                req = Request(
                    f"http://127.0.0.1:{server.server_port}/product_proposals/execute",
                    data=json.dumps({"id": "proposal-3"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req, timeout=2)

                self.assertEqual(ctx.exception.code, 500)
                payload = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["type"], "server_error")

                proposals_after = {item["id"]: item for item in proposal_store.list()}
                self.assertEqual(proposals_after["proposal-1"]["status"], "approved")
                self.assertEqual(proposals_after["proposal-2"]["status"], "building")
                self.assertEqual(len([p for p in proposals_after.values() if p["status"] in {"approved", "building", "ready_to_launch"}]), 2)
                self.assertEqual(launch_store.list(), [])
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
