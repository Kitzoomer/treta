import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.scheduler import DailyScheduler
from core.scheduler_state import load_scheduler_state


class _FakeBus:
    def __init__(self):
        self.events = []

    def push(self, event):
        self.events.append(event)


class SchedulerPersistenceTest(unittest.TestCase):
    @patch.dict(os.environ, {"TRETA_TIMEZONE": "UTC", "TRETA_SCAN_HOUR": "9"}, clear=False)
    def test_scheduler_persists_last_run_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                run_time = datetime(2024, 1, 1, 10, 30, tzinfo=ZoneInfo("UTC"))

                first = DailyScheduler(now_fn=lambda: run_time)
                first_bus = _FakeBus()
                first._bus = first_bus
                first.tick()

                self.assertEqual(len(first_bus.events), 1)

                state_path = Path(tmp_dir) / "scheduler_state.json"
                self.assertTrue(state_path.exists())
                payload = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["last_run_date"], "2024-01-01")
                self.assertEqual(payload["last_run_timestamp"], run_time.isoformat())

                restarted = DailyScheduler(now_fn=lambda: run_time)
                restarted_bus = _FakeBus()
                restarted._bus = restarted_bus
                restarted.tick()

                self.assertEqual(len(restarted_bus.events), 0)

    @patch.dict(os.environ, {"TRETA_TIMEZONE": "UTC", "TRETA_SCAN_HOUR": "9"}, clear=False)
    def test_scheduler_does_not_double_trigger_same_day_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                first_run_time = datetime(2024, 1, 1, 9, 1, tzinfo=ZoneInfo("UTC"))
                second_run_time = datetime(2024, 1, 1, 11, 0, tzinfo=ZoneInfo("UTC"))

                first = DailyScheduler(now_fn=lambda: first_run_time)
                first_bus = _FakeBus()
                first._bus = first_bus
                first.tick()
                self.assertEqual(len(first_bus.events), 1)

                restarted = DailyScheduler(now_fn=lambda: second_run_time)
                restarted_bus = _FakeBus()
                restarted._bus = restarted_bus
                restarted.tick()

                self.assertEqual(restarted_bus.events, [])

    def test_scheduler_state_corrupt_file_recovers_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"TRETA_DATA_DIR": tmp_dir}, clear=False):
                state_path = Path(tmp_dir) / "scheduler_state.json"
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text("{not-json", encoding="utf-8")

                state = load_scheduler_state()

                self.assertEqual(state, {})
                self.assertFalse(state_path.exists())
                quarantined = list(Path(tmp_dir).glob("scheduler_state.json*.corrupt"))
                self.assertEqual(len(quarantined), 1)


if __name__ == "__main__":
    unittest.main()
