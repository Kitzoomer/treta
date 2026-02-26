import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.scheduler import DailyScheduler


class _FakeBus:
    def __init__(self):
        self.events = []

    def push(self, event):
        self.events.append(event)


class DailySchedulerBasicTest(unittest.TestCase):
    @patch.dict(os.environ, {"TRETA_TIMEZONE": "UTC", "TRETA_SCAN_HOUR": "9"}, clear=False)
    def test_tick_runs_immediately_after_scheduled_hour_once_per_day(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                scheduler = DailyScheduler(now_fn=lambda: datetime(2024, 1, 1, 10, 30, tzinfo=ZoneInfo("UTC")))
                bus = _FakeBus()
                scheduler._bus = bus

                scheduler.tick()
                scheduler.tick()

                self.assertEqual(len(bus.events), 1)
                self.assertEqual(bus.events[0].type, "RunInfoproductScan")
                self.assertTrue(bus.events[0].request_id)
                self.assertEqual(bus.events[0].payload.get("request_id"), bus.events[0].request_id)

    @patch.dict(os.environ, {"TRETA_TIMEZONE": "UTC", "TRETA_SCAN_HOUR": "9"}, clear=False)
    def test_tick_does_not_run_before_scheduled_hour(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                scheduler = DailyScheduler(now_fn=lambda: datetime(2024, 1, 1, 8, 59, tzinfo=ZoneInfo("UTC")))
                bus = _FakeBus()
                scheduler._bus = bus

                scheduler.tick()

                self.assertEqual(bus.events, [])


if __name__ == "__main__":
    unittest.main()
