from __future__ import annotations

import unittest


class SchedulerSmokeTest(unittest.TestCase):
    def test_scheduler_tick_smoke(self) -> None:
        try:
            from core.bus import EventBus
            from core.scheduler import DailyScheduler
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"scheduler module unavailable: {exc}")

        bus = EventBus()
        scheduler = DailyScheduler(bus=bus)
        scheduler.tick()

        self.assertIsNotNone(scheduler._next_scan_at)


if __name__ == "__main__":
    unittest.main()
