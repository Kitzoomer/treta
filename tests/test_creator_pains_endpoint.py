import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from core.bus import EventBus
from core.ipc_http import start_http_server
from core.migrations.runner import run_migrations
from core.storage import Storage


class CreatorPainsEndpointTest(unittest.TestCase):
    def test_get_creator_pains_returns_latest_analyses(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)

                with storage._lock:
                    storage.conn.execute(
                        """
                        INSERT INTO creator_pain_analysis (
                            id, reddit_signal_id, pain_category, monetization_level, urgency_score, analyzed_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "analysis-1",
                            "signal-1",
                            "pricing",
                            "high",
                            0.91,
                            "2026-01-01T00:00:00+00:00",
                        ),
                    )
                    storage.conn.commit()

                server = start_http_server(host="127.0.0.1", port=0, bus=EventBus(), storage=storage)
                try:
                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/pains", timeout=2) as response:
                        payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(payload["ok"])
                    self.assertIsNone(payload["error"])
                    self.assertEqual(len(payload["data"]), 1)
                    self.assertEqual(payload["data"][0]["pain_category"], "pricing")
                    self.assertIn("request_id", payload)
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
