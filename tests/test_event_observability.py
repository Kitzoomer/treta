import json
import tempfile
import unittest
from urllib.request import Request, urlopen
from unittest.mock import patch

from core.app import TretaApp
from core.events import Event


class EventObservabilityTest(unittest.TestCase):
    def test_debug_recent_events_exposes_processed_entries(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                app = TretaApp()
                app.dispatcher.handle(Event(type="ListOpportunities", payload={}, source="test", request_id="req-1", trace_id="tr-1", event_id="ev-1"))
                server = app.start_http_server(host="127.0.0.1", port=0)
                try:
                    with urlopen(f"http://127.0.0.1:{server.server_port}/debug/events/recent?limit=5", timeout=3) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()

                self.assertTrue(payload["ok"])
                items = payload["data"]["items"]
                self.assertGreaterEqual(len(items), 1)
                self.assertEqual(items[0]["event_id"], "ev-1")
                self.assertIn("status", items[0])

    def test_correlation_id_contains_event_id_for_decision(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                app = TretaApp()
                event = Event(
                    type="EvaluateOpportunity",
                    payload={"money": 8, "growth": 6, "energy": 3, "health": 5, "relationships": 4, "risk": 2},
                    source="test",
                    request_id="req-2",
                    trace_id="tr-2",
                    event_id="ev-2",
                )
                app.dispatcher.handle(event)
                row = app.storage.conn.execute(
                    "SELECT correlation_id FROM decision_logs ORDER BY id DESC LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIn("event:ev-2", str(row[0]))


if __name__ == "__main__":
    unittest.main()
