import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from core.bus import EventBus
from core.creator_intelligence.launch_tracker import CreatorLaunchTracker
from core.ipc_http import start_http_server
from core.migrations.runner import get_current_version, run_migrations
from core.storage import Storage


class CreatorLaunchTrackerAndEndpointsTest(unittest.TestCase):
    def _seed_offer_draft(self, storage: Storage, offer_id: str = "offer-1"):
        with storage._lock:
            storage.conn.execute(
                """
                INSERT INTO creator_offer_drafts (
                    id,
                    suggestion_id,
                    pain_category,
                    monetization_level,
                    headline,
                    subheadline,
                    core_promise,
                    who_its_for,
                    whats_inside,
                    outcomes,
                    objections,
                    faq,
                    price_anchor,
                    suggested_price,
                    gumroad_description_md,
                    generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer_id,
                    "suggestion-1",
                    "pricing",
                    "high",
                    "headline",
                    "sub",
                    "promise",
                    "audience",
                    json.dumps(["item"]),
                    json.dumps(["outcome"]),
                    json.dumps(["objection"]),
                    json.dumps([{"q": "q", "a": "a"}]),
                    "$99",
                    "$49",
                    "md",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            storage.conn.commit()
        return offer_id

    def test_migration_v8_and_register_and_sale_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                self.assertGreaterEqual(get_current_version(storage.conn), 8)

                self._seed_offer_draft(storage)
                tracker = CreatorLaunchTracker(storage=storage)

                launch = tracker.register_launch(offer_id="offer-1", price=49, notes="launch")
                self.assertEqual(launch["sales"], 0)
                self.assertEqual(launch["revenue"], 0.0)

                updated = tracker.record_sale(launch["id"], quantity=2)
                self.assertEqual(updated["sales"], 2)
                self.assertEqual(updated["revenue"], 98.0)

                summary = tracker.get_performance_summary()
                self.assertEqual(summary["top_category_by_revenue"], "pricing")
                self.assertGreaterEqual(len(summary["categories"]), 1)
                first = summary["categories"][0]
                self.assertEqual(first["pain_category"], "pricing")
                self.assertEqual(first["total_sales"], 2)
                self.assertEqual(first["total_revenue"], 98.0)

    def test_launch_endpoints_return_standard_envelope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                self._seed_offer_draft(storage)

                server = start_http_server(host="127.0.0.1", port=0, bus=EventBus(), storage=storage)
                try:
                    register_request = Request(
                        f"http://127.0.0.1:{server.server_port}/creator/launches/register",
                        data=json.dumps({"offer_id": "offer-1", "price": 49, "notes": "n"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(register_request, timeout=2) as response:
                        register_payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(register_payload["ok"])
                    self.assertIsNone(register_payload["error"])
                    launch_id = register_payload["data"]["id"]

                    sale_request = Request(
                        f"http://127.0.0.1:{server.server_port}/creator/launches/{launch_id}/sale",
                        data=json.dumps({"quantity": 3}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(sale_request, timeout=2) as response:
                        sale_payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(sale_payload["ok"])
                    self.assertIsNone(sale_payload["error"])
                    self.assertEqual(sale_payload["data"]["sales"], 3)
                    self.assertEqual(sale_payload["data"]["revenue"], 147.0)

                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/launches", timeout=2) as response:
                        list_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(list_payload["ok"])
                    self.assertIn("items", list_payload["data"])
                    self.assertGreaterEqual(len(list_payload["data"]["items"]), 1)

                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/launches/summary", timeout=2) as response:
                        summary_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(summary_payload["ok"])
                    self.assertIn("categories", summary_payload["data"])
                    self.assertEqual(summary_payload["data"]["top_category_by_revenue"], "pricing")
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
