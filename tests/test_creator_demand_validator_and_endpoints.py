import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from core.bus import EventBus
from core.creator_intelligence.demand_validator import CreatorDemandValidator
from core.ipc_http import start_http_server
from core.migrations.runner import run_migrations
from core.storage import Storage


class CreatorDemandValidatorAndEndpointsTest(unittest.TestCase):
    def _seed_analysis_rows(self, storage: Storage):
        rows = [
            ("analysis-1", "signal-1", "pricing", "high", 0.95, "2026-01-01T00:00:00+00:00"),
            ("analysis-2", "signal-2", "pricing", "high", 0.85, "2026-01-01T00:01:00+00:00"),
            ("analysis-3", "signal-3", "pricing", "medium", 0.75, "2026-01-01T00:02:00+00:00"),
            ("analysis-4", "signal-4", "retainers", "low", 0.35, "2026-01-01T00:03:00+00:00"),
        ]
        with storage._lock:
            storage.conn.executemany(
                """
                INSERT INTO creator_pain_analysis (
                    id, reddit_signal_id, pain_category, monetization_level, urgency_score, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            storage.conn.commit()

    def test_validate_generates_records_with_score_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                self._seed_analysis_rows(storage)

                validator = CreatorDemandValidator(storage=storage)
                created = validator.validate()

                self.assertGreaterEqual(len(created), 2)
                pricing_row = next(item for item in created if item["pain_category"] == "pricing")
                self.assertIn(pricing_row["demand_strength"], {"strong", "moderate", "weak"})
                self.assertGreaterEqual(pricing_row["launch_priority_score"], 0.0)
                self.assertLessEqual(pricing_row["launch_priority_score"], 1.0)
                self.assertIn(pricing_row["recommended_action"], {"launch_now", "test_with_post", "ignore"})

                with storage._lock:
                    persisted_count = storage.conn.execute(
                        "SELECT COUNT(*) FROM creator_demand_validations"
                    ).fetchone()[0]
                self.assertEqual(persisted_count, len(created))

    def test_demand_endpoints_use_standard_envelope(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                storage = Storage()
                run_migrations(storage.conn)
                self._seed_analysis_rows(storage)

                server = start_http_server(host="127.0.0.1", port=0, bus=EventBus(), storage=storage)
                try:
                    request = Request(
                        f"http://127.0.0.1:{server.server_port}/creator/demand/validate",
                        data=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=2) as response:
                        validate_payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(validate_payload["ok"])
                    self.assertIsNone(validate_payload["error"])
                    self.assertIn("request_id", validate_payload)
                    self.assertIn("items", validate_payload["data"])
                    self.assertGreaterEqual(len(validate_payload["data"]["items"]), 1)

                    with urlopen(f"http://127.0.0.1:{server.server_port}/creator/demand?limit=20", timeout=2) as response:
                        list_payload = json.loads(response.read().decode("utf-8"))

                    self.assertTrue(list_payload["ok"])
                    self.assertIsNone(list_payload["error"])
                    self.assertIn("request_id", list_payload)
                    self.assertIn("items", list_payload["data"])
                    self.assertGreaterEqual(len(list_payload["data"]["items"]), 1)
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
