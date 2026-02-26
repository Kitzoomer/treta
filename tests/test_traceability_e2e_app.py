import json
import os
import tempfile
import unittest
from unittest.mock import patch
import uuid
from urllib.request import Request, urlopen

from core.app import TretaApp


class TretaAppTraceabilityE2ETest(unittest.TestCase):
    def _drain_bus_once(self, app: TretaApp, max_events: int = 20) -> None:
        for _ in range(max_events):
            event = app.bus.pop(timeout=0.1)
            if event is None:
                return
            app.dispatcher.handle(event)

    def test_real_app_persists_decision_logs_and_scheduler_sets_request_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {
                    "TRETA_DATA_DIR": tmp_dir,
                    "TRETA_TIMEZONE": "UTC",
                    "TRETA_SCAN_HOUR": "0",
                },
                clear=False,
            ):
                app = TretaApp()
                server = app.start_http_server(host="127.0.0.1", port=0)
                try:
                    opportunity = app.opportunity_store.add(
                        source="test",
                        title="E2E traceability",
                        summary="decision log persistence",
                        opportunity={
                            "money": 8,
                            "growth": 7,
                            "energy": 2,
                            "health": 7,
                            "relationships": 6,
                            "risk": 2,
                        },
                    )

                    request_id = "req-e2e-evaluate-1"
                    request = Request(
                        f"http://127.0.0.1:{server.server_port}/opportunities/evaluate",
                        data=json.dumps({"id": opportunity["id"]}).encode("utf-8"),
                        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
                        method="POST",
                    )
                    with urlopen(request, timeout=3) as response:
                        self.assertEqual(response.status, 200)

                    self._drain_bus_once(app)

                    logs = app.storage.list_decision_logs(limit=100)
                    self.assertTrue(
                        any(
                            item.get("engine") == "DecisionEngine" and item.get("request_id") == request_id
                            for item in logs
                        )
                    )

                    with urlopen(f"http://127.0.0.1:{server.server_port}/strategy/decide", timeout=3) as response:
                        self.assertEqual(response.status, 200)

                    self._drain_bus_once(app)

                    strategy_logs = app.storage.list_recent_decision_logs(limit=100, decision_type="strategy_action")
                    self.assertTrue(len(strategy_logs) > 0)

                    app.scheduler.tick()
                    scheduler_event = app.bus.pop(timeout=0.2)
                    self.assertIsNotNone(scheduler_event)
                    self.assertTrue(scheduler_event.request_id)
                    self.assertEqual(scheduler_event.payload.get("request_id"), scheduler_event.request_id)
                    uuid.UUID(scheduler_event.request_id)
                finally:
                    server.shutdown()
                    server.server_close()


if __name__ == "__main__":
    unittest.main()
