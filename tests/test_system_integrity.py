import json
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from core.ipc_http import start_http_server

from core.system_integrity import compute_system_integrity
from core.version import VERSION


class SystemIntegrityTest(unittest.TestCase):
    def test_healthy_empty_state(self):
        report = compute_system_integrity([], [], [])

        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["issues"], [])
        self.assertEqual(
            report["counts"],
            {"proposals": 0, "plans": 0, "launches": 0, "issues": 0},
        )

    def test_orphan_plan(self):
        plans = [{"plan_id": "plan-1", "proposal_id": "proposal-missing"}]

        report = compute_system_integrity([], plans, [])

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["counts"]["issues"], 1)
        self.assertEqual(report["issues"][0]["type"], "orphan_plan")
        self.assertEqual(report["issues"][0]["severity"], "warning")

    def test_missing_plan_for_approved_proposal(self):
        proposals = [{"id": "proposal-1", "status": "approved"}]

        report = compute_system_integrity(proposals, [], [])

        self.assertEqual(report["status"], "critical")
        self.assertEqual(report["issues"][0]["type"], "missing_plan")
        self.assertEqual(report["issues"][0]["severity"], "critical")

    def test_launch_without_proposal(self):
        launches = [{"id": "launch-1", "proposal_id": "proposal-missing"}]

        report = compute_system_integrity([], [], launches)

        self.assertEqual(report["status"], "critical")
        issue_types = {issue["type"] for issue in report["issues"]}
        self.assertIn("launch_without_proposal", issue_types)
        self.assertIn("launch_without_plan", issue_types)

    def test_archived_with_active_artifacts(self):
        proposals = [{"id": "proposal-1", "status": "archived"}]
        plans = [{"plan_id": "plan-1", "proposal_id": "proposal-1"}]

        report = compute_system_integrity(proposals, plans, [])

        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["issues"][0]["type"], "archived_with_active_artifacts")
        self.assertEqual(report["issues"][0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()


class _OkStore:
    def __init__(self, items):
        self._items = items

    def list(self, *args, **kwargs):
        return self._items


class _BoomStore:
    def list(self, *args, **kwargs):
        raise RuntimeError("boom")


class SystemIntegrityEndpointTest(unittest.TestCase):
    def test_system_integrity_returns_version(self):
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

            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload["data"].get("version"), VERSION)
        finally:
            server.shutdown()
            server.server_close()

    def test_system_integrity_returns_503_when_store_data_unavailable(self):
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
            self.assertEqual(payload["error"]["code"], "integrity_data_unavailable")
        finally:
            server.shutdown()
            server.server_close()
