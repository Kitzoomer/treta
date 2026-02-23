import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.bus import EventBus
from core.creator_intelligence.offer_service import CreatorOfferService
from core.ipc_http import start_http_server
from core.migrations.runner import run_migrations
from core.storage import Storage


class CreatorOfferServiceAndEndpointsTest(unittest.TestCase):
    def _seed_suggestion(self, storage: Storage, suggestion_id: str = "suggestion-1") -> str:
        with storage._lock:
            storage.conn.execute(
                """
                INSERT INTO creator_product_suggestions (
                    id, pain_category, frequency, avg_urgency, monetization_level,
                    suggested_product, positioning_angle, estimated_price_range, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    suggestion_id,
                    "pricing",
                    5,
                    0.9,
                    "medium",
                    "Pricing Calculator + Rate Guide",
                    "Charge confidently using benchmark-backed creator rates.",
                    "29-59",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            storage.conn.commit()
        return suggestion_id

    def test_generate_offer_draft_creates_record_with_markdown(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                suggestion_id = self._seed_suggestion(storage)

                service = CreatorOfferService(storage=storage)
                draft = service.generate_offer_draft(suggestion_id=suggestion_id)

                self.assertTrue(draft["id"])
                self.assertEqual(draft["suggestion_id"], suggestion_id)
                self.assertTrue(draft["gumroad_description_md"].strip())

                with storage._lock:
                    count = storage.conn.execute(
                        "SELECT COUNT(*) FROM creator_offer_drafts WHERE id = ?",
                        (draft["id"],),
                    ).fetchone()[0]
                self.assertEqual(count, 1)

    def test_offer_endpoints_return_standard_envelope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                suggestion_id = self._seed_suggestion(storage)

                server = start_http_server(host="127.0.0.1", port=0, bus=EventBus(), storage=storage)
                try:
                    request = Request(
                        f"http://127.0.0.1:{server.server_port}/creator/offers/generate",
                        data=json.dumps({"suggestion_id": suggestion_id}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=2) as response:
                        generate_payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(generate_payload["ok"])
                    self.assertIsNone(generate_payload["error"])
                    self.assertIn("request_id", generate_payload)
                    draft_id = generate_payload["data"]["id"]

                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/offers?limit=20", timeout=2) as response:
                        list_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(list_payload["ok"])
                    self.assertIsNone(list_payload["error"])
                    self.assertIn("items", list_payload["data"])
                    self.assertGreaterEqual(len(list_payload["data"]["items"]), 1)

                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/offers/{draft_id}", timeout=2) as response:
                        get_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(get_payload["ok"])
                    self.assertIsNone(get_payload["error"])
                    self.assertEqual(get_payload["data"]["id"], draft_id)

                    try:
                        with urlopen(f"http://127.0.0.1:{server.server_port}/creator/offers/missing", timeout=2) as response:
                            _ = response
                        self.fail("expected HTTPError for missing offer")
                    except HTTPError as exc:
                        payload = json.loads(exc.read().decode("utf-8"))
                        self.assertFalse(payload["ok"])
                        self.assertIsNotNone(payload["error"])
                        self.assertIn("request_id", payload)
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
